from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import Customer, CustomerOTP, Game, Reward, GameAttempt, Coupon

class CustomerEmailAuthAndGameplayTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.game, _ = Game.objects.get_or_create(key='spin', defaults={'name': 'Lucky Spin', 'active': True})
        self.quiz, _ = Game.objects.get_or_create(key='quiz', defaults={'name': 'Food Quiz', 'active': True})
        self.reward = Reward.objects.filter(percentage=15, active=True).first()
        if not self.reward:
            self.reward = Reward.objects.create(percentage=15, weight=50, active=True, minimum_spend=199, max_discount=50)

    def test_send_email_otp_success(self):
        response = self.client.post('/api/customer/send-otp/', {'email': 'diner@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('dev_otp', response.data)
        self.assertEqual(response.data['email'], 'diner@example.com')
        self.assertTrue(CustomerOTP.objects.filter(email='diner@example.com').exists())

    def test_send_email_otp_invalid_email(self):
        response = self.client.post('/api/customer/send-otp/', {'email': 'invalid-email-format'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_email_otp_cooldown(self):
        res1 = self.client.post('/api/customer/send-otp/', {'email': 'guest1@example.com'}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        # Immediate second request triggers cooldown
        res2 = self.client.post('/api/customer/send-otp/', {'email': 'guest1@example.com'}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_verify_email_otp_and_play_restriction(self):
        # 1. Send OTP
        res = self.client.post('/api/customer/send-otp/', {'email': 'guest2@example.com'}, format='json')
        otp = res.data.get('dev_otp') or CustomerOTP.objects.filter(email='guest2@example.com').latest('created_at').otp_code

        # 2. Verify bad OTP
        bad_res = self.client.post('/api/customer/verify-otp/', {'email': 'guest2@example.com', 'otp': '000000'}, format='json')
        self.assertEqual(bad_res.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Verify correct OTP
        verify_res = self.client.post('/api/customer/verify-otp/', {'email': 'guest2@example.com', 'otp': otp}, format='json')
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)
        token = verify_res.data['token']
        self.assertTrue(verify_res.data['customer']['can_play'])

        # 4. Check profile
        me_res = self.client.get('/api/customer/me/', HTTP_X_CUSTOMER_TOKEN=token)
        self.assertEqual(me_res.status_code, status.HTTP_200_OK)
        self.assertEqual(me_res.data['customer']['email'], 'guest2@example.com')
        self.assertTrue(me_res.data['customer']['can_play'])

        # 5. Play game first time -> succeeds and creates coupon
        play_res = self.client.post('/api/game/play/', {'game': 'spin'}, format='json', HTTP_X_CUSTOMER_TOKEN=token)
        self.assertEqual(play_res.status_code, status.HTTP_200_OK)
        self.assertFalse(play_res.data['can_play'])
        self.assertEqual(Coupon.objects.filter(email='guest2@example.com').count(), 1)
        self.assertEqual(GameAttempt.objects.filter(email='guest2@example.com').count(), 1)

        # 6. Second play within 24 hours -> rejected with 429
        repeat_res = self.client.post('/api/game/play/', {'game': 'spin'}, format='json', HTTP_X_CUSTOMER_TOKEN=token)
        self.assertEqual(repeat_res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('already played', repeat_res.data['error'])

        # 7. Login again from new session / device with same email -> still blocked from playing
        CustomerOTP.objects.all().delete()
        self.client.post('/api/customer/send-otp/', {'email': 'guest2@example.com'}, format='json')
        new_otp = CustomerOTP.objects.filter(email='guest2@example.com').latest('created_at').otp_code
        new_verify = self.client.post('/api/customer/verify-otp/', {'email': 'guest2@example.com', 'otp': new_otp}, format='json')
        self.assertEqual(new_verify.status_code, status.HTTP_200_OK)
        new_token = new_verify.data['token']
        self.assertFalse(new_verify.data['customer']['can_play'])

        repeat2 = self.client.post('/api/game/play/', {'game': 'quiz', 'answer': 'Shawarma'}, format='json', HTTP_X_CUSTOMER_TOKEN=new_token)
        self.assertEqual(repeat2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # 8. Saved coupons are retrievable by email
        coupons_res = self.client.get('/api/coupons/', HTTP_X_CUSTOMER_TOKEN=new_token)
        self.assertEqual(coupons_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(coupons_res.data), 1)

        # 9. Another email address CAN play
        self.client.post('/api/customer/send-otp/', {'email': 'another@example.com'}, format='json')
        other_otp = CustomerOTP.objects.filter(email='another@example.com').latest('created_at').otp_code
        other_verify = self.client.post('/api/customer/verify-otp/', {'email': 'another@example.com', 'otp': other_otp}, format='json')
        self.assertEqual(other_verify.status_code, status.HTTP_200_OK)
        other_token = other_verify.data['token']
        self.assertTrue(other_verify.data['customer']['can_play'])
        other_play = self.client.post('/api/game/play/', {'game': 'spin'}, format='json', HTTP_X_CUSTOMER_TOKEN=other_token)
        self.assertEqual(other_play.status_code, status.HTTP_200_OK)

    def test_customer_reward_probabilities_configuration(self):
        """
        Verify the exact reward probabilities requested:
        - 25% jackpot has exactly 2% chance (20 / 1000)
        - Below 10%: 88% chance (880 / 1000):
          - 1%: 35% (350 weight)
          - 2%: 22% (220 weight)
          - 3%: 12% (120 weight)
          - 5%: 8% (80 weight)
          - 8%: 6% (60 weight)
          - Unlucky (0%): 5% (50 weight)
        - 10% and above: 12% chance (120 / 1000):
          - 10%: 4% (40 weight)
          - 12%: 3% (30 weight)
          - 15%: 2% (20 weight)
          - 20%: 1% (10 weight)
          - 25%: 2% (20 weight)
        Total = 100% (1000 weight)
        """
        active_rewards = Reward.objects.filter(active=True)
        total_weight = sum(r.weight for r in active_rewards)
        self.assertEqual(total_weight, 1000)

        reward_map = {r.percentage: r.weight for r in active_rewards}
        # Below 10% tiers (88% total)
        self.assertEqual(reward_map[1], 350)   # 35%
        self.assertEqual(reward_map[2], 220)   # 22%
        self.assertEqual(reward_map[3], 120)   # 12%
        self.assertEqual(reward_map[5], 80)    # 8%
        self.assertEqual(reward_map[8], 60)    # 6%
        self.assertEqual(reward_map[0], 50)    # 5% Unlucky
        below_10_weight = sum(reward_map[p] for p in [0, 1, 2, 3, 5, 8])
        self.assertEqual(below_10_weight, 880) # 88% below 10

        # 10% and above tiers (12% total)
        self.assertEqual(reward_map[10], 40)   # 4%
        self.assertEqual(reward_map[12], 30)   # 3%
        self.assertEqual(reward_map[15], 20)   # 2%
        self.assertEqual(reward_map[20], 10)   # 1%
        self.assertEqual(reward_map[25], 20)   # 2% Jackpot (exact 2% requested)
        above_or_equal_10_weight = sum(reward_map[p] for p in [10, 12, 15, 20, 25])
        self.assertEqual(above_or_equal_10_weight, 120) # 12% at or above 10

    def test_unlucky_reward_creates_no_coupon(self):
        """When user lands on Unlucky (0%), no coupon is created and is_unlucky is True."""
        Reward.objects.all().update(active=False)
        unlucky_reward = Reward.objects.create(percentage=0, weight=50, active=True)

        self.client.post('/api/customer/send-otp/', {'email': 'unlucky_user@example.com'}, format='json')
        otp = CustomerOTP.objects.filter(email='unlucky_user@example.com').latest('created_at').otp_code
        v_res = self.client.post('/api/customer/verify-otp/', {'email': 'unlucky_user@example.com', 'otp': otp}, format='json')
        token = v_res.data['token']

        play_res = self.client.post('/api/game/play/', {'game': 'spin'}, format='json', HTTP_X_CUSTOMER_TOKEN=token)
        self.assertEqual(play_res.status_code, status.HTTP_200_OK)
        self.assertTrue(play_res.data['is_unlucky'])
        self.assertEqual(play_res.data['reward'], 0)
        self.assertIsNone(play_res.data['coupon_code'])
        self.assertEqual(Coupon.objects.filter(email='unlucky_user@example.com').count(), 0)

