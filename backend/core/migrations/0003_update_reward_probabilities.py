from django.db import migrations

def update_reward_probabilities(apps, schema_editor):
    Reward = apps.get_model('core', 'Reward')
    # Exact probabilities requested:
    # 25% jackpot has exactly 2% chance (20 / 1000)
    # Below 10%: 88% chance (880 / 1000): 1%: 35%, 2%: 22%, 3%: 12%, 5%: 8%, 8%: 6%, Unlucky: 5%
    # 10% and above: 12% chance (120 / 1000): 10%: 4%, 12%: 3%, 15%: 2%, 20%: 1%, 25%: 2%
    # Total = 1000 (100%)
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

    configured_percentages = set()
    for pct, weight in reward_config:
        configured_percentages.add(pct)
        Reward.objects.update_or_create(
            percentage=pct,
            defaults={
                'weight': weight,
                'active': True,
                'max_discount': 50,
                'minimum_spend': 199,
            }
        )

    # Deactivate any rewards not in configured percentages
    Reward.objects.exclude(percentage__in=configured_percentages).update(active=False, weight=0)

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_coupon_code_plain'),
    ]

    operations = [
        migrations.RunPython(update_reward_probabilities, reverse_code=migrations.RunPython.noop),
    ]
