from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from .models import User, Auction, Bid, Category, Comment, Watchlist
from .forms import NewCommentForm, NewListingForm, NewBidForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import timedelta
from django.db.models import Max, F, Case, When, BooleanField, Value
from django.db.models import Q

def index(request):
    return render(request, "auctions/index.html", {
        "auctions": Auction.objects.filter(closed=False).order_by('-creation_date')
    })

def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        # Check if authentication successful
        if user is not None:
            login(request, user)
            # return sucessful message
            messages.success(request, f'Welcome, {username}. Login successfully.')

            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "auctions/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "auctions/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "auctions/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "auctions/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "auctions/register.html")


def categories(request):
    return render(request, "auctions/categories.html", {
        "categories": Category.objects.all()
    })


def category(request, category_id):
    try:
        # get a list of all active listing of the category
        auctions = Auction.objects.filter(category=category_id, closed=False).order_by('-creation_date')
         
    except Auction.DoesNotExist:
        return render(request, "auctions/error.html", {
            "code": 404,
            "message": f"The category does not exist."
        })
   
    try:
        # get the category
        category = Category.objects.get(pk=category_id)

    except Category.DoesNotExist:
        return render(request, "auctions/error.html", {
            "code": 404,
            "message": f"The category does not exist."
        })

    return render(request, "auctions/category.html", {
        "auctions": auctions,
        "category": category
    })


@login_required(login_url="login") 
def watchlist(request):
    # check the existance of the user's watchlist
    try:
        watchlist = Watchlist.objects.get(user=request.user)
        auctions = watchlist.auctions.all().order_by('-id')
        # calculate the number of items in the watchlist
        watchingNum = watchlist.auctions.all().count()

    except ObjectDoesNotExist:
        # if watchlist does not exist
        watchlist = None
        auctions = None
        watchingNum = 0
    

    return render(request, "auctions/watchlist.html", {
        # return the listings in the watchlist
        "watchlist": watchlist,
        "auctions": auctions,
        "watchingNum": watchingNum
    })

@login_required(login_url="login") 
def mybiddings(request):
    #check the existance of the user's watchlist
    try:
        mybiddings= Bid.objects.filter(bider=request.user.id).values('auction').distinct()
        auction_numbers = mybiddings.values_list('auction', flat=True)
        unique_auctions = Auction.objects.filter(id__in=auction_numbers)
        auction_status_dict = {}
        for auction_id in auction_numbers:
            try:
                highest_bidder = Bid.objects.filter(auction=auction_id).order_by('-bid_price').first().bider
                is_highest_bidder = highest_bidder == request.user
                auction_status_dict[auction_id] = is_highest_bidder
            except Bid.DoesNotExist:
                # Handle the case where there are no bids for the auction
                auction_status_dict[auction_id] = False

    except ObjectDoesNotExist:
        # if watchlist does not exist
        mybiddings = None
        unique_auctions = None
        auction_numbers = 0

    return render(request, "auctions/mybiddings.html", {
        # return the listings in the watchlist
        "mybiddings": mybiddings,
        "unique_auctions": unique_auctions,
        "Num": len(unique_auctions),
        "auction_status_dict": auction_status_dict
    })

    
@login_required(login_url="login")
def create(request):
    # check the request method is POST
    if request.method == "POST":
        # create a form instance with POST data
        form = NewListingForm(request.POST, request.FILES)

        # check whether it's valid
        if form.is_valid():
            # form["end_date"] = form["end_date"] - timedelta(hours=5)
            print(form)
            # save the form from data to model
            new_listing = form.save(commit=False)
            # save the request user as seller
            new_listing.seller = request.user
            # save the starting bid as current price
            new_listing.current_bid = form.cleaned_data['starting_bid']
            new_listing.save()

            # return sucessful message
            messages.success(request, 'Create the auction listing successfully.')

            # redirect the user to the index page
            return HttpResponseRedirect(reverse("index"))

        else:
            form = NewListingForm()

            # if the form is invalid, re-render the page with existing information
            messages.error(request, 'The form is invalid. Please resumbit.')
            return render(request, "auctions/create.html", {
                "form": form
            })
    
    # if the request method is GET
    else:
        form = NewListingForm()
        return render(request, "auctions/create.html", {
            "form": form
        })


def listing(request, auction_id):  
    try:
        # get the auction listing by id
        auction = Auction.objects.get(pk=auction_id)
        
    except Auction.DoesNotExist:
        return render(request, "auctions/error.html", {
            "code": 404,
            "message": "The auction does not exist."
        })

    # set watching flag be False as default
    watching = False
    # set the highest bidder is None as default    
    highest_bidder = None

    # check if the auction in the watchlist
    if request.user.is_authenticated and Watchlist.objects.filter(user=request.user, auctions=auction):
        watching = True
    
    # get the page request user
    user = request.user

    # get the number of bids
    bid_Num = Bid.objects.filter(auction=auction_id).count()

    # get all comments of the auction
    comments = Comment.objects.filter(auction=auction_id).order_by("-cm_date")

    # get the highest bids of the aunction
    highest_bid = Bid.objects.filter(auction=auction_id).order_by("-bid_price").first()
    
    # check the request method is POST
    if request.method == "GET":
        form = NewBidForm()
        commentForm = NewCommentForm()

        # check if the auction listing is not closed
        if not auction.closed:
            return render(request, "auctions/listing.html", {
            "auction": auction,
            "form": form,
            "user": user,
            "bid_Num": bid_Num,
            "commentForm": commentForm,
            "comments": comments,
            "watching": watching
            }) 

        # the auction is closed
        else:
            # check the if there is bid for the auction listing
            if highest_bid is None:
                messages.info(request, 'The bid is closed and no bidder.')
                return render(request, "auctions/listing.html", {
                    "auction": auction,
                    "form": form,
                    "user": user,
                    "bid_Num": bid_Num,
                    "highest_bidder": highest_bidder,
                    "commentForm": commentForm,
                    "comments": comments,
                    "watching": watching
                })

            else:
                # assign the highest_bidder
                highest_bidder = highest_bid.bider

                # check the request user if the bid winner    
                if user == highest_bidder:
                    messages.info(request, 'Congratulation. You won the bid.')
                else:
                    messages.info(request, f'The winner of the bid is {highest_bidder.username}')

                return render(request, "auctions/listing.html", {
                "auction": auction,
                "form": form,
                "user": user,
                "highest_bidder": highest_bidder,
                "bid_Num": bid_Num,
                "commentForm": commentForm,
                "comments": comments,
                "watching": watching
                })

    
    # listing itself does not support POST method
    else:
        return render(request, "auctions/error.html", {
            "code": 405,
            "message": "The POST method is not allowed."
        })
        
        

@login_required(login_url="login")
def close(request, auction_id):
    # check to handle POST method only
    if request.method == "POST":
        # check the existence auction
        try:
            # get the auction listing by id
            auction = Auction.objects.get(pk=auction_id)

        except Auction.DoesNotExist:
            return render(request, "auctions/error.html", {
                "code": 404,
                "message": "The auction does not exist."
            })

        # check whether the request user who create the listing
        if request.user != auction.seller:
            messages.error(request, 'The request is not allowed.')
            return HttpResponseRedirect(reverse("listing", args=(auction.id,)))

        else:

            # update and save the closed status
            auction.closed = True
            auction.save()
            
            # pop up the message
            messages.success(request, 'The auction listing is closed sucessfully.')
            return HttpResponseRedirect(reverse("listing", args=(auction.id,)))

    # close view not support GET method    
    else:
        return render(request, "auctions/error.html", {
            "code": 405,
            "message": "The GET method is not allowed."
        })
        

@login_required(login_url="login")
def bid(request, auction_id):
    # Check to handle POST method only
    if request.method == "POST":
        # Check the existence of the auction
        try:
            # Get the auction listing by id
            auction = Auction.objects.get(pk=auction_id)
        except Auction.DoesNotExist:
            return render(request, "auctions/error.html", {
                "code": 404,
                "message": "The auction does not exist."
            })

        # Get the highest bid of the auction
        highest_bid = Bid.objects.filter(auction=auction_id).order_by("-bid_price").first()
        # Check if the current user is the highest bidder
        if highest_bid is not None:
            is_highest_bidder = highest_bid.bider_id== request.user.id
        else:
            is_highest_bidder = False
        # Get the current highest bid price
        highest_bid_price = highest_bid.bid_price if highest_bid else auction.current_bid

        # Create a form instance with POST data
        form = NewBidForm(request.POST, request.FILES)

        # Check if the auction is closed
        if auction.closed:
            messages.error(request, 'The auction listing is closed.')
            return HttpResponseRedirect(reverse("listing", args=(auction.id,)))
        
        # The auction listing is active
        else:
            # Check whether the form is valid
            if form.is_valid():
                # Isolate content from the clean version of form data
                bid_price = form.cleaned_data["bid_price"]
                # Validate the bid offer
                if bid_price > auction.starting_bid and bid_price > highest_bid_price:
                    # Check if the current user is the highest bidder
                    if is_highest_bidder:
                        messages.error(request, 'You are already the highest bidder.')
                    else:

                        if highest_bid is not None:
                            email = User.objects.filter(id=highest_bid.bider_id).values_list('email', flat=True).first()
                            sendEmail(email,auction.title, bid_price)
                        # Save the form data to the model
                        new_bid = form.save(commit=False)
                        # Save the request user as the bidder
                        new_bid.bider_id = request.user.id
                        # Get and save the auction
                        new_bid.auction = auction
                        print("New bid",new_bid)
                        new_bid.save()
                        # Update and save the current price
                        auction.current_bid = bid_price
                        auction.save()
                        # Return a successful message
                        messages.success(request, 'Your bid offer is made successfully.')

                # Handle invalid bid offer
                else:
                    # If the bid is invalid, populate the message
                    messages.error(request, 'Please submit a valid bid offer. Your bid offer must be higher than the starting bid and current price.')

                # Valid form, redirect the user to the listing page 
                return HttpResponseRedirect(reverse("listing", args=(auction.id,)))

            else:
                # If the form is invalid, re-render the page with existing information
                messages.error(request, 'Please submit a valid bid offer. Your bid offer must be higher than the starting bid and current price.')

                # Redirect the user to the listing page
                return HttpResponseRedirect(reverse("listing", args=(auction.id,)))

    # Bid view does not support the GET method
    else:
        return render(request, "auctions/error.html", {
            "code": 405,
            "message": "The GET method is not allowed."
        })

@login_required(login_url="login")
def comment(request, auction_id):
    # check to handle POST method only
    if request.method == "POST":

        # check the existence auction
        try:
            # get the auction listing by id
            auction = Auction.objects.get(pk=auction_id)     
            
        except Auction.DoesNotExist:
            return render(request, "auctions/error.html", {
                "code": 404,
                "message": "The auction does not exist."
            })
            
        # create a form instance with POST data
        form = NewCommentForm(request.POST, request.FILES)

        # check whether it's valid
        if form.is_valid():
            # save the comment from from data to model
            new_comment = form.save(commit=False)
            # save the request user who leaves the comment
            new_comment.user = request.user
            # save the auction for this comment
            new_comment.auction = auction
            new_comment.save()
            # return sucessful message
            messages.success(request, 'Your comment is received sucessfully.')
            return HttpResponseRedirect(reverse("listing", args=(auction.id,)))
        
        # handle invalid comment form
        else:
            # if the form is invalid
            messages.error(request, 'Please submit a valid comment.')
     
    # comment view do not support get method
    else:
        return render(request, "auctions/error.html", {
            "code": 405,
            "message": "The GET method is not allowed."
        })


@login_required(login_url="login")
def addWatchlist(request, auction_id):   
    # check to handle POST method only
    if request.method == "POST":
        # check the existence auction
        try:
            # get the auction listing by id
            auction = Auction.objects.get(pk=auction_id)     
            
        except Auction.DoesNotExist:
            return render(request, "auctions/error.html", {
                "code": 404,
                "message": "The auction does not exist."
            })

        # check the existance of the user's watchlist
        try:
            watchlist = Watchlist.objects.get(user=request.user)

        except ObjectDoesNotExist:
            # if no watchlist, create an watchlist object for the user
            watchlist = Watchlist.objects.create(user=request.user)
        
        # check if the item exists in the user's watchlist
        if Watchlist.objects.filter(user=request.user, auctions=auction):
            messages.error(request, 'You already added in your watchlist')
            return HttpResponseRedirect(reverse("listing", args=(auction.id,)))

        # if the item is not in the watchlist
        watchlist.auctions.add(auction)
            
        # return sucessful message
        messages.success(request, 'The listing is added to your Watchlist.')

        return HttpResponseRedirect(reverse("listing", args=(auction.id,)))
        
     
    # addWatchlist view do not support get method
    else:
        return render(request, "auctions/error.html", {
            "code": 405,
            "message": "The GET method is not allowed."
        })


@login_required(login_url="login")
def removeWatchlist(request, auction_id):   
    # check to handle POST method only
    if request.method == "POST":
        # check the existence auction
        try:
            # get the auction listing by id
            auction = Auction.objects.get(pk=auction_id)     
            
        except Auction.DoesNotExist:
            return render(request, "auctions/error.html", {
                "code": 404,
                "message": "The auction does not exist."
            })
        
        # check if the item exists in the user's watchlist
        if Watchlist.objects.filter(user=request.user, auctions=auction):
            # get the user's watchlist
            watchlist = Watchlist.objects.get(user=request.user)
           
            # delete the auction from the users watchlist
            watchlist.auctions.remove(auction)
                
            # return sucessful message
            messages.success(request, 'The listing is removed from your watchlist.')

            return HttpResponseRedirect(reverse("listing", args=(auction.id,)))
        
        else:
            # return error message
            messages.success(request, 'You cannot remove the listing not in your watchlist.')

            return HttpResponseRedirect(reverse("listing", args=(auction.id,)))
   
     
    # removeWatchlist view do not support get method
    else:
        return render(request, "auctions/error.html", {
            "code": 405,
            "message": "The GET method is not allowed."
        })

def sendEmail(email, title ,new):
    sender_email = "cloudcomputing691@gmail.com"
    receiver_email = email
    subject = "Auction Listing Outbid"
    body = "Hello Auctioner, we have exciting updates about the auction! Unfortunately, someone has outbid your previous offer on the item "+title +". The New bid price is $"+ str(new) +". Feel free to return to our application and consider placing a higher bid if you still have your eye on the item. Thank you for your enthusiasm! Sincerely, Auctioner Team"


    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    smtp_username = "cloudcomputing691@gmail.com"
    smtp_password = "mepj bvfr gmyw tcik"

    # Create the email message
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(smtp_username, smtp_password)

    # Send the email
    server.sendmail(sender_email, receiver_email, message.as_string())

    # Quit the server
    server.quit()