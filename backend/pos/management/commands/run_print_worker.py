import time
from django.core.management.base import BaseCommand
from pos.printer import process_pending_print_jobs

class Command(BaseCommand):
    help = 'Runs the Rayara Cafe thermal print queue daemon'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process pending jobs once and exit')
        parser.add_argument('--interval', type=float, default=2.0, help='Polling interval in seconds')

    def handle(self, *args, **options):
        once = options.get('once', False)
        interval = options.get('interval', 2.0)

        self.stdout.write(self.style.SUCCESS("Rayara Thermal Print Worker started..."))
        if once:
            count = process_pending_print_jobs()
            self.stdout.write(f"Processed {count} print jobs.")
            return

        try:
            while True:
                count = process_pending_print_jobs()
                if count > 0:
                    self.stdout.write(f"Processed {count} print jobs.")
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("Print worker stopped.")

