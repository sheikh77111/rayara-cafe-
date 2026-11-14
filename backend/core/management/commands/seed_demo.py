from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import MenuCategory, MenuItem, Game, Reward

class Command(BaseCommand):
    help = 'Create initial Rayara demo menu, games, 20-option reward probabilities and demo users.'

    def handle(self, *args, **kwargs):
        # 1. Menu Categories & Items
        data = {
            'Shawarma': [('Chicken Shawarma', 'Freshly prepared chicken shawarma', 120)],
            'Grills': [
                ('Chicken Shawaya', 'Whole grilled chicken; set price before launch', 0),
                ('Alfaham', 'Smoky charcoal grilled chicken; set price before launch', 0)
            ],
            'Evening Snacks': [('Evening Snacks', 'Ask staff for today’s selection', 0)],
            'Tea & Coffee': [('Tea', 'Freshly brewed tea', 15), ('Coffee', 'Hot coffee', 25)]
        }
        for idx, (cat, items) in enumerate(data.items()):
            c, _ = MenuCategory.objects.get_or_create(name=cat, defaults={'sort_order': idx})
            for name, desc, price in items:
                MenuItem.objects.get_or_create(category=c, name=name, defaults={'description': desc, 'price': price, 'available': price > 0})

        # 2. Games
        for key, name in [('spin', 'Lucky Spin'), ('scratch', 'Mystery Scratch'), ('quiz', 'Food Quiz')]:
            Game.objects.get_or_create(key=key, defaults={'name': name})

        # 3. Rewards configuration for the 20 spin options (Probabilities total 1000 = 100%)
        # 25% jackpot: exactly 2% chance (20 weight)
        # Below 10%: 88% chance (880 weight): 1%: 35%, 2%: 22%, 3%: 12%, 5%: 8%, 8%: 6%, Unlucky: 5%
        # 10% and above: 12% chance (120 weight): 10%: 4%, 12%: 3%, 15%: 2%, 20%: 1%, 25%: 2%
        reward_config = [
            (1, 350),   # 1% (35% probability)
            (2, 220),   # 2% (22% probability)
            (3, 120),   # 3% (12% probability)
            (5, 80),    # 5% (8% probability)
            (0, 50),    # Null/Unlucky (5% probability)
            (8, 60),    # 8% (6% probability)
            (10, 40),   # 10% (4% probability)
            (12, 30),   # 12% (3% probability)
            (15, 20),   # 15% (2% probability)
            (20, 10),   # 20% (1% probability)
            (25, 20),   # 25% (2% probability - rare jackpot!)
        ]

        # Reset existing rewards to match new 20-slice distribution
        Reward.objects.all().delete()
        for pct, weight in reward_config:
            Reward.objects.create(
                percentage=pct,
                weight=weight,
                max_discount=50,
                minimum_spend=199,
                active=True
            )

        # 4. Demo Users for /owner and /staff testing
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@rayara.local', 'admin123')
            self.stdout.write(self.style.SUCCESS('Created demo owner/superuser: admin (password: admin123)'))

        if not User.objects.filter(username='staff1').exists():
            staff_user = User.objects.create_user('staff1', 'staff@rayara.local', 'staff123')
            staff_user.is_staff = True
            staff_user.save()
            self.stdout.write(self.style.SUCCESS('Created demo staff user: staff1 (password: staff123)'))

        self.stdout.write(self.style.SUCCESS('Rayara 20-option rewards ready. 25% configured as ultra-rare (0.2% probability).'))
