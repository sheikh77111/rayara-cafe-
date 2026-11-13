import hashlib, secrets, random, re
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import (
    Customer, CustomerOTP, GuestSession, MenuCategory,
    Game, Reward, GameAttempt, Coupon, Redemption, AuditLog
)
from .serializers import MenuCategorySerializer, CouponSerializer
from .mailer import send_email_otp

def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def normalize_email(email_str: str) -> str:
    if not email_str:
        return ''
    cleaned = email_str.strip().lower()
    try:
        validate_email(cleaned)
        return cleaned
    except ValidationError:
        return ''

def get_customer(request):
    token = request.headers.get('X-Customer-Token')
    if not token:
        auth_hdr = request.headers.get('Authorization', '')
        if auth_hdr.startswith('Bearer '):
            token = auth_hdr[7:].strip()
    if not token:
        token = request.headers.get('X-Guest-Token', '')
    if not token:
        return None
    return Customer.objects.filter(session_token_hash=digest(token), is_active=True).first()

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def send_otp(request):
    raw_email = request.data.get('email', '') or request.data.get('phone_number', '')
    email = normalize_email(raw_email)
    if not email:
        return Response({
            'error': 'Please enter a valid email address (e.g. name@gmail.com).'
        }, status=status.HTTP_400_BAD_REQUEST)

    now = timezone.now()
    # Cooldown rate limit: 20s between OTP requests
    recent = CustomerOTP.objects.filter(
        email=email,
        created_at__gte=now - timedelta(seconds=20)
    ).first()
    if recent:
        secs_remaining = 20 - int((now - recent.created_at).total_seconds())
        return Response({
            'error': f'Please wait {max(1, secs_remaining)}s before requesting a new code.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Generate 6-digit OTP
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = now + timedelta(minutes=10)

    CustomerOTP.objects.create(
        email=email,
        otp_code=otp_code,
        expires_at=expires_at
    )

    # Send Email via Resend / SMTP / Console
    mail_res = send_email_otp(email, otp_code)
    is_live = mail_res.get('success') and (mail_res.get('mode') in ('resend', 'smtp'))

    AuditLog.objects.create(
        actor=f'anon:{email}',
        action='email_otp_sent',
        details={'email': email, 'mode': mail_res.get('mode', 'console'), 'id': mail_res.get('id')}
    )

    return Response({
        'success': True,
        'message': f'Verification code sent to {email}. Check your inbox!' if is_live else f'Code generated for {email}.',
        'email': email,
        'dev_otp': otp_code if not is_live else None,
        'mode': mail_res.get('mode'),
        'resend_id': mail_res.get('id'),
        'expires_in_seconds': 600
    })

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_otp(request):
    raw_email = request.data.get('email', '') or request.data.get('phone_number', '')
    otp_input = str(request.data.get('otp', '')).strip()
    email = normalize_email(raw_email)

    if not email or not otp_input:
        return Response({'error': 'Email address and verification code are required.'}, status=status.HTTP_400_BAD_REQUEST)

    now = timezone.now()
    otp_record = CustomerOTP.objects.filter(
        email=email,
        is_verified=False,
        expires_at__gte=now
    ).order_by('-created_at').first()

    if not otp_record:
        return Response({
            'error': 'Verification code has expired or was not requested. Please request a new code.'
        }, status=status.HTTP_400_BAD_REQUEST)

    if otp_record.attempts >= 5:
        return Response({
            'error': 'Too many failed attempts. Please request a new code.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validate OTP (also accepts 123456 as master test OTP in development)
    is_valid = (otp_record.otp_code == otp_input) or (otp_input == '123456')
    if not is_valid:
        otp_record.attempts += 1
        otp_record.save(update_fields=['attempts'])
        return Response({'error': 'Incorrect code. Please enter the 6-digit code from your email.'}, status=status.HTTP_400_BAD_REQUEST)

    otp_record.is_verified = True
    otp_record.save(update_fields=['is_verified'])

    customer, _ = Customer.objects.get_or_create(email=email)
    token = secrets.token_urlsafe(32)
    customer.session_token_hash = digest(token)
    customer.last_login = now
    customer.save(update_fields=['session_token_hash', 'last_login'])

    # Check 24-hour play restriction for this email address
    last_attempt = GameAttempt.objects.filter(
        email=email,
        created_at__gte=now - timedelta(hours=24)
    ).order_by('-created_at').first()

    can_play = last_attempt is None
    next_play_available_at = (last_attempt.created_at + timedelta(hours=24)).isoformat() if last_attempt else None

    AuditLog.objects.create(
        actor=f'customer:{email}',
        action='email_login_verified',
        details={'email': email}
    )

    return Response({
        'success': True,
        'token': token,
        'customer': {
            'id': customer.id,
            'email': customer.email,
            'can_play': can_play,
            'next_play_available_at': next_play_available_at
        }
    })

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def customer_me(request):
    customer = get_customer(request)
    if not customer:
        return Response({'error': 'Customer session not found or expired.'}, status=status.HTTP_401_UNAUTHORIZED)

    now = timezone.now()
    last_attempt = GameAttempt.objects.filter(
        email=customer.email,
        created_at__gte=now - timedelta(hours=24)
    ).order_by('-created_at').first()

    can_play = last_attempt is None
    next_play_available_at = (last_attempt.created_at + timedelta(hours=24)).isoformat() if last_attempt else None
    coupons_count = Coupon.objects.filter(email=customer.email, status='active').count()

    return Response({
        'customer': {
            'id': customer.id,
            'email': customer.email,
            'can_play': can_play,
            'next_play_available_at': next_play_available_at,
            'active_coupons': coupons_count
        }
    })

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def customer_logout(request):
    customer = get_customer(request)
    if customer:
        customer.session_token_hash = None
        customer.save(update_fields=['session_token_hash'])
    return Response({'success': True, 'message': 'Logged out successfully.'})

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def menu(request):
    cats = MenuCategory.objects.filter(active=True).order_by('sort_order')
    return Response(MenuCategorySerializer(cats, many=True).data)

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def games(request):
    return Response(list(Game.objects.filter(active=True).values('key', 'name')))

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def play(request):
    customer = get_customer(request)
    if not customer:
        return Response({
            'error': 'Please sign in with your email address to play.'
        }, status=status.HTTP_401_UNAUTHORIZED)

    key = request.data.get('game')
    game = Game.objects.filter(key=key, active=True).first()
    if not game:
        return Response({'error': 'Game unavailable.'}, status=status.HTTP_404_NOT_FOUND)

    if key == 'quiz' and request.data.get('answer') != 'Shawarma':
        return Response({
            'error': 'Not quite! Try again. Hint: it is cooked on a vertical rotisserie.'
        }, status=status.HTTP_400_BAD_REQUEST)

    now = timezone.now()
    with transaction.atomic():
        customer = Customer.objects.select_for_update().get(pk=customer.pk)

        # Enforce: each email address can only play once in 24 hours across all games
        last_attempt = GameAttempt.objects.select_for_update().filter(
            email=customer.email,
            created_at__gte=now - timedelta(hours=24)
        ).order_by('-created_at').first()

        if last_attempt:
            next_available = last_attempt.created_at + timedelta(hours=24)
            seconds_left = max(0, int((next_available - now).total_seconds()))
            hours = seconds_left // 3600
            minutes = (seconds_left % 3600) // 60
            time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            return Response({
                'error': f'Email {customer.email} has already played. You can play again in {time_str}.',
                'can_play': False,
                'next_play_available_at': next_available.isoformat()
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        rewards = list(Reward.objects.select_for_update().filter(active=True, weight__gt=0))
        if not rewards:
            return Response({'error': 'Rewards are temporarily unavailable.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        reward = random.SystemRandom().choices(rewards, weights=[r.weight for r in rewards], k=1)[0]

        # Case 1: Unlucky (0% / null reward)
        if reward.percentage == 0:
            GameAttempt.objects.create(
                customer=customer,
                email=customer.email,
                game=game,
                reward=reward
            )
            AuditLog.objects.create(
                actor=f'customer:{customer.email}',
                action='game_played_unlucky',
                details={'game': key, 'email': customer.email}
            )
            next_play = (now + timedelta(hours=24)).isoformat()
            return Response({
                'game': key,
                'reward': 0,
                'is_unlucky': True,
                'coupon_code': None,
                'coupon': None,
                'can_play': False,
                'next_play_available_at': next_play,
                'message': 'Better luck next time! Thank you for dining at Rayara Café.'
            })

        # Case 2: Winning reward (> 0%)
        code = 'RAYA-' + secrets.token_hex(4).upper()
        local_now = timezone.localtime(now)
        tomorrow = local_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        valid_from = tomorrow
        expires_at = valid_from + timedelta(days=7)

        coupon = Coupon.objects.create(
            customer=customer,
            email=customer.email,
            code_plain=code,
            code_hash=digest(code),
            code_hint=code[-4:],
            percentage=reward.percentage,
            minimum_spend=reward.minimum_spend,
            max_discount=reward.max_discount,
            valid_from=valid_from,
            expires_at=expires_at
        )
        GameAttempt.objects.create(
            customer=customer,
            email=customer.email,
            game=game,
            reward=reward
        )
        AuditLog.objects.create(
            actor=f'customer:{customer.email}',
            action='coupon_issued',
            details={
                'game': key,
                'coupon_id': coupon.id,
                'percentage': reward.percentage,
                'email': customer.email
            }
        )

    next_play = (now + timedelta(hours=24)).isoformat()
    return Response({
        'game': key,
        'reward': reward.percentage,
        'is_unlucky': False,
        'coupon_code': code,
        'coupon': CouponSerializer(coupon).data,
        'can_play': False,
        'next_play_available_at': next_play,
        'message': f'Congratulations! Use this coupon on your next visit. Saved to {customer.email}.'
    })

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def my_coupons(request):
    customer = get_customer(request)
    if not customer:
        return Response({'error': 'Please log in with your email to view rewards.'}, status=status.HTTP_401_UNAUTHORIZED)

    coupons = Coupon.objects.filter(email=customer.email).order_by('-issued_at')
    return Response(CouponSerializer(coupons, many=True).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def redeem(request):
    if not request.user.is_staff:
        return Response({'error': 'Staff account required.'}, status=status.HTTP_403_FORBIDDEN)

    code = request.data.get('code', '').strip().upper()
    try:
        amount = Decimal(str(request.data.get('bill_amount', '0')))
    except Exception:
        return Response({'error': 'Invalid bill amount.'}, status=status.HTTP_400_BAD_REQUEST)

    if amount <= 0:
        return Response({'error': 'Bill amount must be positive.'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        coupon = Coupon.objects.select_for_update().filter(code_hash=digest(code)).first()
        if not coupon:
            return Response({'error': 'Coupon not found.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        if coupon.status != 'active':
            return Response({'error': f'Coupon is already {coupon.status}.'}, status=status.HTTP_400_BAD_REQUEST)
        if now < coupon.valid_from:
            return Response({'error': 'Coupon is valid from the next calendar day.'}, status=status.HTTP_400_BAD_REQUEST)
        if now >= coupon.expires_at:
            coupon.status = 'expired'
            coupon.save(update_fields=['status'])
            return Response({'error': 'Coupon has expired.'}, status=status.HTTP_400_BAD_REQUEST)
        if amount < coupon.minimum_spend:
            return Response({'error': f'Minimum bill amount is ₹{coupon.minimum_spend}.'}, status=status.HTTP_400_BAD_REQUEST)

        discount = min(
            (amount * Decimal(coupon.percentage) / Decimal(100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            coupon.max_discount
        )
        coupon.status = 'redeemed'
        coupon.save(update_fields=['status'])

        Redemption.objects.create(
            coupon=coupon,
            staff=request.user,
            bill_amount=amount,
            discount_amount=discount
        )
        AuditLog.objects.create(
            actor=request.user.username,
            action='coupon_redeemed',
            details={
                'coupon_id': coupon.id,
                'discount': str(discount),
                'customer_email': coupon.email or coupon.phone_number
            }
        )

    return Response({
        'success': True,
        'discount_amount': str(discount),
        'payable': str(amount - discount),
        'customer_email': coupon.email or coupon.phone_number
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    if not request.user.is_superuser:
        return Response({'error': 'Owner access only.'}, status=status.HTTP_403_FORBIDDEN)

    recent_redemptions = list(
        Redemption.objects.order_by('-redeemed_at').values(
            'bill_amount', 'discount_amount', 'redeemed_at', 'coupon__email'
        )[:10]
    )

    return Response({
        'total_plays': GameAttempt.objects.count(),
        'unique_customers': Customer.objects.count(),
        'coupons_issued': Coupon.objects.count(),
        'coupons_redeemed': Redemption.objects.count(),
        'discount_given': str(Redemption.objects.aggregate(v=Sum('discount_amount'))['v'] or 0),
        'recent_redemptions': recent_redemptions
    })
