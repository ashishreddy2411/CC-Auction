from django.apps import AppConfig

class AuctionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auctions'

    def ready(self):
        print("Auctions app is ready!")  # Add this line
        import auctions.signals
        