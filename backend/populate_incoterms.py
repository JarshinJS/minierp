import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from apps.foreign_trade.models import Incoterm

INCOTERMS = [
    {"code": "EXW", "name": "Ex Works", "description": "Seller makes the goods available at their premises."},
    {"code": "FCA", "name": "Free Carrier", "description": "Seller delivers goods to the carrier or another person nominated by the buyer at the seller's premises or another named place."},
    {"code": "CPT", "name": "Carriage Paid To", "description": "Seller delivers the goods to the carrier or another person nominated by the seller at an agreed place."},
    {"code": "CIP", "name": "Carriage and Insurance Paid To", "description": "Seller has same responsibilities as CPT, but they also contract for insurance cover against the buyer's risk of loss of or damage to the goods during the carriage."},
    {"code": "DAP", "name": "Delivered at Place", "description": "Seller delivers when the goods are placed at the disposal of the buyer on the arriving means of transport ready for unloading at the named place of destination."},
    {"code": "DPU", "name": "Delivered at Place Unloaded", "description": "Seller delivers when the goods, once unloaded are placed at the disposal of the buyer at a named terminal at the named port or place of destination."},
    {"code": "DDP", "name": "Delivered Duty Paid", "description": "Seller delivers the goods when the goods are placed at the disposal of the buyer, cleared for import on the arriving means of transport ready for unloading at the named place of destination."},
    {"code": "FAS", "name": "Free Alongside Ship", "description": "Seller delivers when the goods are placed alongside the vessel nominated by the buyer at the named port of shipment."},
    {"code": "FOB", "name": "Free On Board", "description": "Seller delivers the goods on board the vessel nominated by the buyer at the named port of shipment or procures the goods already so delivered."},
    {"code": "CFR", "name": "Cost and Freight", "description": "Seller delivers the goods on board the vessel or procures the goods already so delivered."},
    {"code": "CIF", "name": "Cost, Insurance and Freight", "description": "Seller delivers the goods on board the vessel or procures the goods already so delivered. The seller also contracts for insurance cover against the buyer's risk of loss of or damage to the goods during the carriage."}
]

def run():
    print("Populating Incoterms...")
    for item in INCOTERMS:
        obj, created = Incoterm.objects.update_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "description": item["description"]
            }
        )
        if created:
            print(f"Created {item['code']}")
        else:
            print(f"Updated {item['code']}")
    print("Done!")

if __name__ == "__main__":
    run()
