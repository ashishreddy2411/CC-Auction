from django.utils import timezone
from .models import Auction, User, Watchlist
from .views import sendEmail
from datetime import timedelta

class CheckAuctionEndMiddleware:
    processed_auctions = set()

    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        self.timeout_auction_items()
        self.check_auction_items()
        return response

    def check_auction_items(self):
        current_time = timezone.now()
        expired_items = Auction.objects.filter(end_date__lte=current_time, closed=False)
        for item in expired_items:
            item.closed = True
            highest_bid = item.auction_bids.order_by('-bid_price').first()
            watchlisters = Watchlist.objects.filter(auctions__id=item.id).values_list('id', flat=True)
            if highest_bid != None:
                email = User.objects.filter(id=highest_bid.bider_id).values_list('email', flat=True).first()
                sendEmail(email, item.title, highest_bid.bid_price,1)
                item.save()
                for bid_id in watchlisters:
                    if bid_id != highest_bid.bider_id:
                        email = User.objects.filter(id=bid_id).values_list('email', flat=True).first()
                        sendEmail(email,item.title, item.current_bid,3)

    def timeout_auction_items(self):
        current_time = timezone.now()
        thirty_minutes_later = current_time + timedelta(minutes=30)
        expiring_items = Auction.objects.filter(end_date__lte=thirty_minutes_later, closed=False)
        for item in expiring_items:
            if item not in self.processed_auctions:
                highest_bid = item.auction_bids.order_by('-bid_price').first()
                watchlisters = Watchlist.objects.filter(auctions__id=item.id).values_list('id', flat=True)
                all_bids = item.auction_bids.order_by('-bid_price')
                for bid in all_bids:
                    if bid.bid_price != highest_bid.bid_price and len(all_bids) > 1:
                        email = User.objects.filter(id=bid.bider_id).values_list('email', flat=True).first()
                        sendEmail(email, item.title, highest_bid.bid_price,2)
                for bid_id in watchlisters:
                        if bid_id != highest_bid.bider_id:
                            email = User.objects.filter(id=bid_id).values_list('email', flat=True).first()
                            sendEmail(email,item.title, item.current_bid,3)
                self.processed_auctions.add(item)