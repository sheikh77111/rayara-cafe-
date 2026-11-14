import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from pos.models import Category, Product, ProductOptionGroup, ProductOption

def run():
    print("Beginning Full Rayara Cafe Menu Population...")

    # Define Categories
    categories_data = [
        ("Shawarma", 1),
        ("Alfaham", 2),
        ("Chicken Shawaya", 3),
        ("Momos", 4),
        ("Tea & Coffee", 5),
        ("Fresh Juices", 6),
        ("Milkshakes", 7),
        ("Soft Drinks & Water", 8),
        ("Evening Snacks", 9),
        ("French Fries & Loaded Fries", 10),
    ]

    cat_map = {}
    for name, order in categories_data:
        cat, created = Category.objects.get_or_create(name=name, defaults={'display_order': order, 'is_active': True})
        cat.display_order = order
        cat.is_active = True
        cat.save()
        cat_map[name] = cat
        print(f"Category: {name} (Order: {order})")

    # 1. SHAWARMA
    shawarma_items = [
        ("Normal Chicken Shawarma", "Tender spiced chicken rolled in choice of Kuboos or Rumali.", Decimal('110.00')),
        ("Full Chicken Shawarma", "Loaded all-chicken portion wrapped fresh with garlic paste.", Decimal('150.00')),
        ("Special Chicken Shawarma", "Chef's signature all-meat shawarma blend with Arabian seasoning.", Decimal('170.00')),
        ("Extra Chicken Shawarma", "Extra-large chicken portion with pickled cucumber and fries.", Decimal('160.00')),
    ]
    for name, desc, price in shawarma_items:
        prod, _ = Product.objects.update_or_create(
            name=name, category=cat_map["Shawarma"],
            defaults={'description': desc, 'price': price, 'is_available': True, 'is_active': True}
        )
        # Options
        prod.option_groups.all().delete()
        g_bread = ProductOptionGroup.objects.create(product=prod, name="Choose Bread", selection_type="single", is_required=True, display_order=1)
        ProductOption.objects.create(group=g_bread, name="Rumali", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
        ProductOption.objects.create(group=g_bread, name="Kuboos", price_modifier=Decimal('0.00'), is_default=False, display_order=2)

        g_add = ProductOptionGroup.objects.create(product=prod, name="Customizations", selection_type="multiple", is_required=False, display_order=2)
        ProductOption.objects.create(group=g_add, name="Extra Mayonnaise", price_modifier=Decimal('0.00'), display_order=1)
        ProductOption.objects.create(group=g_add, name="Extra Garlic Dip", price_modifier=Decimal('0.00'), display_order=2)
        ProductOption.objects.create(group=g_add, name="Extra Spicy", price_modifier=Decimal('0.00'), display_order=3)
        ProductOption.objects.create(group=g_add, name="Extra Chicken", price_modifier=Decimal('35.00'), display_order=4)
        ProductOption.objects.create(group=g_add, name="Extra Cheese", price_modifier=Decimal('25.00'), display_order=5)

    # 2. ALFAHAM
    alfaham_items = [
        ("Normal Alfaham (Original)", "Classic Arabian charcoal-grilled chicken infused with whole spices.", Decimal('140.00'), Decimal('130.00'), Decimal('380.00')),
        ("Peri Peri Alfaham (Spicy)", "Fiery African bird's eye peri-peri marinade grilled over natural charcoal.", Decimal('150.00'), Decimal('140.00'), Decimal('410.00')),
        ("Honey Alfaham (Glazed)", "Succulent grilled chicken basted with golden organic honey glaze.", Decimal('160.00'), Decimal('150.00'), Decimal('430.00')),
    ]
    for name, desc, base_q, half_mod, full_mod in alfaham_items:
        prod, _ = Product.objects.update_or_create(
            name=name, category=cat_map["Alfaham"],
            defaults={'description': desc, 'price': base_q, 'is_available': True, 'is_active': True}
        )
        prod.option_groups.all().delete()
        g_size = ProductOptionGroup.objects.create(product=prod, name="Portion Size", selection_type="single", is_required=True, display_order=1)
        ProductOption.objects.create(group=g_size, name="Quarter", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
        ProductOption.objects.create(group=g_size, name="Half", price_modifier=half_mod, display_order=2)
        ProductOption.objects.create(group=g_size, name="Full", price_modifier=full_mod, display_order=3)

        g_serv = ProductOptionGroup.objects.create(product=prod, name="Serving Option", selection_type="single", is_required=True, display_order=2)
        ProductOption.objects.create(group=g_serv, name="Rumali", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
        ProductOption.objects.create(group=g_serv, name="Kuboos", price_modifier=Decimal('0.00'), display_order=2)

        g_add = ProductOptionGroup.objects.create(product=prod, name="Add-ons & Dips", selection_type="multiple", is_required=False, display_order=3)
        ProductOption.objects.create(group=g_add, name="Extra Mayonnaise", price_modifier=Decimal('0.00'), display_order=1)
        ProductOption.objects.create(group=g_add, name="Extra Garlic Sauce", price_modifier=Decimal('0.00'), display_order=2)
        ProductOption.objects.create(group=g_add, name="Extra Rumali", price_modifier=Decimal('15.00'), display_order=3)
        ProductOption.objects.create(group=g_add, name="Extra Kuboos", price_modifier=Decimal('12.00'), display_order=4)

    # 3. CHICKEN SHAWAYA
    prod_sw, _ = Product.objects.update_or_create(
        name="Normal Chicken Shawaya", category=cat_map["Chicken Shawaya"],
        defaults={'description': "Rotisserie slow-roasted succulent chicken with crispy seasoned skin.", 'price': Decimal('130.00'), 'is_available': True, 'is_active': True}
    )
    prod_sw.option_groups.all().delete()
    g_sw_size = ProductOptionGroup.objects.create(product=prod_sw, name="Portion Size", selection_type="single", is_required=True, display_order=1)
    ProductOption.objects.create(group=g_sw_size, name="Quarter", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
    ProductOption.objects.create(group=g_sw_size, name="Half", price_modifier=Decimal('120.00'), display_order=2)
    ProductOption.objects.create(group=g_sw_size, name="Full", price_modifier=Decimal('350.00'), display_order=3)

    g_sw_serv = ProductOptionGroup.objects.create(product=prod_sw, name="Serving Bread", selection_type="single", is_required=True, display_order=2)
    ProductOption.objects.create(group=g_sw_serv, name="Rumali", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
    ProductOption.objects.create(group=g_sw_serv, name="Kuboos", price_modifier=Decimal('0.00'), display_order=2)

    g_sw_add = ProductOptionGroup.objects.create(product=prod_sw, name="Add-ons & Dips", selection_type="multiple", is_required=False, display_order=3)
    ProductOption.objects.create(group=g_sw_add, name="Garlic Sauce", price_modifier=Decimal('0.00'), display_order=1)
    ProductOption.objects.create(group=g_sw_add, name="Mayonnaise", price_modifier=Decimal('0.00'), display_order=2)
    ProductOption.objects.create(group=g_sw_add, name="Extra Rumali", price_modifier=Decimal('15.00'), display_order=3)
    ProductOption.objects.create(group=g_sw_add, name="Extra Kuboos", price_modifier=Decimal('12.00'), display_order=4)

    # 4. MOMOS
    momos_items = [
        ("Chicken Momos (Steamed)", "Minced chicken dumplings with shallots and herbs.", Decimal('90.00'), Decimal('70.00')),
        ("Veg Momos (Steamed)", "Finely chopped cabbage, carrots, and sweet bell peppers.", Decimal('80.00'), Decimal('60.00')),
        ("Fried Chicken Momos", "Crisp-fried chicken dumplings with spicy red chili sauce.", Decimal('100.00'), Decimal('80.00')),
        ("Fried Veg Momos", "Golden crispy fried vegetable dumplings.", Decimal('90.00'), Decimal('70.00')),
        ("Peri Peri Momos", "Crispy fried momos dusted in African peri-peri seasoning.", Decimal('110.00'), Decimal('80.00')),
    ]
    for name, desc, base_h, full_add in momos_items:
        prod, _ = Product.objects.update_or_create(
            name=name, category=cat_map["Momos"],
            defaults={'description': desc, 'price': base_h, 'is_available': True, 'is_active': True}
        )
        prod.option_groups.all().delete()
        g_portion = ProductOptionGroup.objects.create(product=prod, name="Portion", selection_type="single", is_required=True, display_order=1)
        ProductOption.objects.create(group=g_portion, name="Half (5 pcs)", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
        ProductOption.objects.create(group=g_portion, name="Full (10 pcs)", price_modifier=full_add, display_order=2)

        g_momo_dips = ProductOptionGroup.objects.create(product=prod, name="Complimentary Dips", selection_type="multiple", is_required=False, display_order=2)
        ProductOption.objects.create(group=g_momo_dips, name="Spicy Schezwan Dip", price_modifier=Decimal('0.00'), display_order=1)
        ProductOption.objects.create(group=g_momo_dips, name="Mayo Dip", price_modifier=Decimal('0.00'), display_order=2)

    # 5. TEA & COFFEE
    tea_items = [
        ("Normal Tea", "Traditional Malabar freshly brewed milk tea.", Decimal('15.00')),
        ("Strong Tea", "Kadak double-decoction brewed tea.", Decimal('20.00')),
        ("Ginger Tea", "Fresh crushed ginger brewed with fragrant tea leaves.", Decimal('20.00')),
        ("Cardamom Tea", "Aromatic crushed green cardamom tea.", Decimal('25.00')),
        ("Chocolate Tea", "Artisanal cocoa-infused rich tea.", Decimal('35.00')),
        ("Lime Tea", "Hot black tea with freshly squeezed lemon juice.", Decimal('20.00')),
        ("Green Tea", "Antioxidant-rich whole leaf green tea.", Decimal('25.00')),
        ("Normal Milk Coffee", "Freshly brewed South Indian filter coffee.", Decimal('25.00')),
    ]
    for name, desc, price in tea_items:
        prod, _ = Product.objects.update_or_create(
            name=name, category=cat_map["Tea & Coffee"],
            defaults={'description': desc, 'price': price, 'is_available': True, 'is_active': True}
        )
        prod.option_groups.all().delete()

    coffee_specials = [
        ("Cappuccino", "Rich espresso shot with steamed velvety milk foam.", Decimal('60.00')),
        ("Chocolate Coffee", "Dark chocolate mocha blend with whipped cream top.", Decimal('70.00')),
    ]
    for name, desc, price in coffee_specials:
        prod, _ = Product.objects.update_or_create(
            name=name, category=cat_map["Tea & Coffee"],
            defaults={'description': desc, 'price': price, 'is_available': True, 'is_active': True}
        )
        prod.option_groups.all().delete()
        g_temp = ProductOptionGroup.objects.create(product=prod, name="Temperature", selection_type="single", is_required=True, display_order=1)
        ProductOption.objects.create(group=g_temp, name="Hot", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
        ProductOption.objects.create(group=g_temp, name="Cold / Iced", price_modifier=Decimal('15.00'), display_order=2)

    # 6. FRESH JUICES
    juice_items = [
        ("Orange Juice", "Freshly squeezed sweet Valencia oranges.", Decimal('70.00')),
        ("Mosambi Juice", "Sweet lime cold-pressed fresh juice.", Decimal('60.00')),
        ("Lemon Juice (Fresh Lime)", "Chilled fresh lime with fresh mint.", Decimal('30.00')),
        ("Pineapple Juice", "Tropical golden pineapple juice.", Decimal('60.00')),
        ("Mango Juice", "Thick chilled Alphonso mango nectar.", Decimal('80.00')),
        ("Watermelon Juice", "Fresh seedless sweet watermelon juice.", Decimal('50.00')),
        ("Apple Juice", "Pure crisp red apple cold-pressed juice.", Decimal('80.00')),
        ("Grape Juice", "Sweet seedless black grape juice.", Decimal('70.00')),
        ("Pomegranate Juice", "Ruby red antioxidant pomegranate juice.", Decimal('90.00')),
        ("Papaya Juice", "Smooth ripe papaya with crushed ice.", Decimal('50.00')),
        ("Guava Juice", "Pink tropical guava blend with salt-chili rim.", Decimal('60.00')),
        ("ABC Juice (Apple Beetroot Carrot)", "Miracle detox wellness booster juice.", Decimal('100.00')),
        ("Carrot Juice", "Freshly extracted sweet organic carrots.", Decimal('70.00')),
        ("Beetroot Juice", "Vitality ruby beetroot juice.", Decimal('60.00')),
    ]
    for name, desc, price in juice_items:
        prod, _ = Product.objects.update_or_create(
            name=name, category=cat_map["Fresh Juices"],
            defaults={'description': desc, 'price': price, 'is_available': True, 'is_active': True}
        )
        prod.option_groups.all().delete()
        g_prep = ProductOptionGroup.objects.create(product=prod, name="Customization", selection_type="multiple", is_required=False, display_order=1)
        ProductOption.objects.create(group=g_prep, name="With Sugar", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
        ProductOption.objects.create(group=g_prep, name="No Sugar", price_modifier=Decimal('0.00'), display_order=2)
        ProductOption.objects.create(group=g_prep, name="Without Ice", price_modifier=Decimal('0.00'), display_order=3)
        ProductOption.objects.create(group=g_prep, name="Extra Ice", price_modifier=Decimal('0.00'), display_order=4)

    # 7. MILKSHAKES & SPECIAL SHAKES
    shakes_items = [
        ("Chocolate Shake", "Rich Belgian chocolate fudge milkshake.", Decimal('90.00')),
        ("Vanilla Shake", "Pure Madagascar vanilla bean milkshake.", Decimal('80.00')),
        ("Strawberry Shake", "Fresh strawberry puree and dairy cream.", Decimal('80.00')),
        ("Mango Shake", "Alphonso mango thick milkshake.", Decimal('90.00')),
        ("Banana Shake", "Fresh Robusta banana milk blend.", Decimal('70.00')),
        ("Oreo Shake", "Loaded with crushed Oreo cookies and chocolate drizzle.", Decimal('110.00')),
        ("KitKat Shake", "Crispy KitKat chocolate wafer milkshake.", Decimal('120.00')),
        ("Snickers Shake", "Peanut butter, nougat, and caramel Snickers thickshake.", Decimal('130.00')),
        ("Dates Shake", "Medjool dates blended with cold whole milk.", Decimal('110.00')),
        ("Badam Shake", "California roasted almond milkshake.", Decimal('110.00')),
        ("Pista Shake", "Royal green pistachio thick shake.", Decimal('120.00')),
        ("Avocado Shake", "Rich butterfruit avocado with natural honey.", Decimal('130.00')),
        ("Tender Coconut Shake", "Fresh elaneer tender coconut pulp and water.", Decimal('120.00')),
        ("Dry Fruit Shake", "Anjeer, cashew, almond, and golden raisin shake.", Decimal('140.00')),
    ]
    for name, desc, price in shakes_items:
        prod, _ = Product.objects.update_or_create(
            name=name, category=cat_map["Milkshakes"],
            defaults={'description': desc, 'price': price, 'is_available': True, 'is_active': True}
        )
        prod.option_groups.all().delete()
        g_sz = ProductOptionGroup.objects.create(product=prod, name="Size", selection_type="single", is_required=True, display_order=1)
        ProductOption.objects.create(group=g_sz, name="Regular", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
        ProductOption.objects.create(group=g_sz, name="Large", price_modifier=Decimal('30.00'), display_order=2)

    # 8. SOFT DRINKS & WATER
    soft_drinks = [
        ("Pepsi", "Chilled carbonated cola beverage.", Decimal('40.00')),
        ("Coca-Cola", "Chilled classic cola bottle.", Decimal('40.00')),
        ("7UP", "Crisp lemon-lime sparkling soda.", Decimal('40.00')),
        ("Mountain Dew", "Citrus blast energizing soft drink.", Decimal('40.00')),
        ("Sprite", "Clean, refreshing lemon-lime soft drink.", Decimal('40.00')),
        ("Fanta", "Bubbly bright orange soda.", Decimal('40.00')),
        ("Mirinda", "Tangy orange flavored soft drink.", Decimal('40.00')),
        ("Mineral Water", "Purified packaged drinking water bottle.", Decimal('20.00')),
    ]
    for name, desc, price in soft_drinks:
        prod, _ = Product.objects.update_or_create(
            name=name, category=cat_map["Soft Drinks & Water"],
            defaults={'description': desc, 'price': price, 'is_available': True, 'is_active': True}
        )
        prod.option_groups.all().delete()

    # 9. EVENING SNACKS
    snack_items = [
        ("Samosa", "Crispy triangle pastry stuffed with spiced potato and peas.", Decimal('15.00')),
        ("Chicken Cutlet", "Golden panko crumb-fried spiced chicken cutlet.", Decimal('25.00')),
        ("Chicken Roll", "Flaky pastry roll filled with shredded chicken masala.", Decimal('30.00')),
        ("Unnakaya", "Kerala traditional spindle-shaped banana snack stuffed with sweet coconut.", Decimal('25.00')),
        ("Pazhampori (Banana Fritters)", "Crispy golden batter-fried ripe Kerala banana.", Decimal('15.00')),
        ("Kalmas", "Thalassery spiced chicken rice dumplings.", Decimal('25.00')),
        ("Egg Puffs", "Flaky multi-layered puff pastry filled with hard-boiled egg masala.", Decimal('25.00')),
        ("Chicken Puffs", "Oven baked crispy puff filled with minced chicken keema.", Decimal('30.00')),
        ("Veg Cutlet", "Crispy spiced potato, carrot, and beetroot cutlet.", Decimal('20.00')),
        ("Parippu Vada", "Crunchy Bengal gram lentil dal fritter.", Decimal('15.00')),
        ("Uzhunnu Vada", "Fluffy crispy urad dal medu vada with curry leaves.", Decimal('15.00')),
        ("Onion Pakoda", "Crisp fried spiced onion fritters.", Decimal('40.00')),
        ("Bread Bajji", "Besan battered fried bread snack.", Decimal('20.00')),
        ("Spring Roll", "Crispy Chinese-style vegetable roll.", Decimal('35.00')),
        ("Chicken Nuggets", "6 pieces golden crispy tender chicken bites.", Decimal('90.00')),
    ]
    for name, desc, price in snack_items:
        prod, _ = Product.objects.update_or_create(
            name=name, category=cat_map["Evening Snacks"],
            defaults={'description': desc, 'price': price, 'is_available': True, 'is_active': True}
        )
        prod.option_groups.all().delete()
        g_snack_dip = ProductOptionGroup.objects.create(product=prod, name="Complimentary Dips", selection_type="multiple", is_required=False, display_order=1)
        ProductOption.objects.create(group=g_snack_dip, name="Tomato Ketchup", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
        ProductOption.objects.create(group=g_snack_dip, name="Mint Chutney", price_modifier=Decimal('0.00'), display_order=2)
        ProductOption.objects.create(group=g_snack_dip, name="Mayonnaise Dip", price_modifier=Decimal('0.00'), display_order=3)

    # 10. FRENCH FRIES & LOADED FRIES
    fries_items = [
        ("Normal Fries (Classic Salted)", "Golden crisp shoestring potato fries with sea salt.", Decimal('80.00')),
        ("Peri Peri Fries", "Crispy fries tossed in zesty peri-peri seasoning.", Decimal('100.00')),
        ("Loaded Fries", "Fries topped with sauteed vegetables and rich sauces.", Decimal('140.00')),
        ("Spicy Loaded Fries", "Tossed with hot chili sauce, jalapeños, and spiced seasonings.", Decimal('150.00')),
        ("Cheesy Loaded Fries", "Smothered in creamy warm melted cheddar cheese sauce.", Decimal('160.00')),
    ]
    for name, desc, price in fries_items:
        prod, _ = Product.objects.update_or_create(
            name=name, category=cat_map["French Fries & Loaded Fries"],
            defaults={'description': desc, 'price': price, 'is_available': True, 'is_active': True}
        )
        prod.option_groups.all().delete()
        g_fries_add = ProductOptionGroup.objects.create(product=prod, name="Add-ons & Dips", selection_type="multiple", is_required=False, display_order=1)
        ProductOption.objects.create(group=g_fries_add, name="Extra Mayonnaise", price_modifier=Decimal('0.00'), is_default=True, display_order=1)
        ProductOption.objects.create(group=g_fries_add, name="Garlic Dip", price_modifier=Decimal('0.00'), display_order=2)
        ProductOption.objects.create(group=g_fries_add, name="Extra Cheese", price_modifier=Decimal('30.00'), display_order=3)
        ProductOption.objects.create(group=g_fries_add, name="Extra Peri Peri Dust", price_modifier=Decimal('10.00'), display_order=4)
        ProductOption.objects.create(group=g_fries_add, name="Chicken Topping", price_modifier=Decimal('40.00'), display_order=5)
        ProductOption.objects.create(group=g_fries_add, name="Jalapenos", price_modifier=Decimal('20.00'), display_order=6)

    # Clean up obsolete placeholder products
    old_cats = Category.objects.exclude(name__in=[c[0] for c in categories_data])
    for oc in old_cats:
        oc.products.update(is_active=False)
        oc.is_active = False
        oc.save()

    total_prods = Product.objects.filter(is_active=True).count()
    total_cats = Category.objects.filter(is_active=True).count()
    total_options = ProductOption.objects.count()
    print(f"COMPLETE! {total_cats} Categories, {total_prods} Active Products, {total_options} Configured Options!")

if __name__ == '__main__':
    run()

