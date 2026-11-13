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

        # 3. Rewards configuration for the 20 spin options
        # 10 slices of 1% (50%), 3 slices of 2% (24%), 2 slices of unlucky 0% (15%)
        # 1 slice of 5% (5%), 1 slice of 8% (3%), 1 slice of 12% (1.8%), 1 slice of 15% (1.0%),
        # 1 slice of 25% (0.2% - ultra rare)
        reward_config = [
            (1, 500),   # 1% (10 slices on wheel)
            (2, 240),   # 2% (3 slices on wheel)
            (0, 150),   # Null/Unlucky (2 slices on wheel)
            (5, 50),    # 5% (1 slice on wheel)
            (8, 30),    # 8% (1 slice on wheel)
            (12, 18),   # 12% (1 slice on wheel)
            (15, 10),   # 15% (1 slice on wheel)
            (25, 2),    # 25% (1 slice on wheel - ultra rare!)
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
