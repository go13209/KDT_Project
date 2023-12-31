from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import Product, Review, Comment
from .forms import ReviewForm, CommentForm
import requests
from bs4 import BeautifulSoup
from django.db.models import Avg
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import HttpResponseRedirect

# Create your views here.
def index_redirect(request):
    return redirect('reviews:index')


def index(request):
    ranking_url = 'https://search.musinsa.com/ranking/best?u_cat_cd='
    res = requests.get(ranking_url)
    soup = BeautifulSoup(res.text, 'html.parser')

    products_ranking = []
    for item in soup.select('.li_inner')[:15]:
        product = Product()
        product.data_id = item.select_one('a.img-block')['href'].split('?')[0].split('/')[-1]
        product.brand = item.select('.article_info > p > a')[0].text.strip()
        product.title = item.select('.article_info > p > a')[1].contents[-1].strip()
        product.photo = item.select('.lazyload')[0]['data-original']
        products_ranking.append(product)
    
    
    showcase_url = "https://www.musinsa.com/app/showcase/lists"
    headers = { "User-Agent": "Mozilla/5.0" }
    showcase_res = requests.get(showcase_url, headers=headers)
    showcase_soup = BeautifulSoup(showcase_res.text, "html.parser")

    showcase_data = []
    for item in showcase_soup.select('.n-card-list .n-card-img')[:3]:
        showcase_link = item.select_one('a')['href']
        showcase_img = item.select_one('img')['src']
        showcase_data.append({'link': showcase_link, 'image': showcase_img})
    
    
    Product.objects.all().delete()

    Product.objects.bulk_create(products_ranking)

    context = {
        'products_ranking': products_ranking,
        'showcase_data': showcase_data,
    }
    return render(request,'reviews/index.html', context)


def search(request):
    query = request.GET.get('query')

    search_url = f'https://www.musinsa.com/search/musinsa/goods?q={query}'
    res = requests.get(search_url)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    products_search = []

    for item in soup.select('.li_inner'):
        product = Product()
        product.brand = item.select('.article_info > p > a')[0].text.strip()
        product.title = item.select('.article_info > p > a')[1].contents[-1].strip()
        product.photo = item.select('.lazyload')[0]['data-original']
        product.data_id = item.select_one('[data-bh-content-no]')['data-bh-content-no']
        products_search.append(product)

    Product.objects.all().delete()

    Product.objects.bulk_create(products_search)

    products = Product.objects.order_by('-pk')
    per_page = 12
    paginator = Paginator(products, per_page)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)

    context = {
        'products': page_obj,
        'products_search': products_search,
        'query': query,
    }
    return render(request,'reviews/search.html', context)


def category(request, category_type):
    if category_type == 'top':
        category_url = 'https://www.musinsa.com/categories/item/001'
        category_title = '상의'
    elif category_type == 'outerwear':
        category_url = 'https://www.musinsa.com/categories/item/002'
        category_title = '아우터'
    elif category_type == 'bottoms':
        category_url = 'https://www.musinsa.com/categories/item/003'
        category_title = '하의'
    elif category_type == 'shoes':
        category_url = 'https://www.musinsa.com/categories/item/005'
        category_title = '신발'

    res = requests.get(category_url)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    products_category = []
    for item in soup.select('#goods_list .li_inner')[:36]:
        product = Product()
        product.data_id = item.select_one('a.img-block')['href'].split('?')[0].split('/')[-1]
        product.brand = item.select('.article_info > p > a')[0].text.strip()
        product.title = item.select('.article_info > p > a')[1].contents[-1].strip()
        product.photo = item.select('.lazyload')[0]['data-original']
        products_category.append(product)


    Product.objects.all().delete()

    Product.objects.bulk_create(products_category)

    products = Product.objects.order_by('-pk')
    per_page = 12
    paginator = Paginator(products, per_page)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)

    context = {
        'products': page_obj,
        'products_category': products_category,
        'category_title': category_title,
    }
    return render(request, 'reviews/category.html', context)


def product_detail(request, data_id):
    if Product.objects.filter(data_id=data_id).exists():
        product = Product.objects.get(data_id=data_id)
        product_exists = True
        selected_review = None
    else:
        selected_review = Review.objects.filter(review_product_id=data_id).first()
        product_exists = False
        product = None

    reviews = Review.objects.filter(review_product_id=data_id).order_by('-pk')
    review_count = len(reviews)
    page = request.GET.get('page', '1')
    paginator = Paginator(reviews, 5)
    page_obj = paginator.get_page(page)
    average_score = reviews.aggregate(Avg('score'))
    

    context = {
        'product_exists': product_exists,
        'product': product,
        'review': selected_review,
        'reviews': page_obj,
        'review_count': review_count,
        'average_score': average_score['score__avg'],
    }
    return render(request, 'reviews/detail.html', context)


@login_required
def create(request, data_id):
    if request.user.is_authenticated:
        if Product.objects.filter(data_id=data_id).exists():
            product = Product.objects.get(data_id=data_id)
            product_exists = True
            selected_review = None
        else:
            selected_review = Review.objects.filter(review_product_id=data_id).first()
            product_exists = False
            product = None

        if request.method == 'POST':
            review_form = ReviewForm(request.POST, request.FILES)
            if review_form.is_valid():
                review = review_form.save(commit=False)
                if Product.objects.filter(data_id=data_id).exists():
                    review.title = product.title
                    review.brand = product.brand
                    review.photo = product.photo
                    review.review_product_id = product.data_id
                else:
                    review.title = selected_review.title
                    review.brand = selected_review.brand
                    review.photo = selected_review.photo
                    review.review_product_id = selected_review.review_product_id

                review.score = int(request.POST['score'])
                review.user = request.user
                review.save()
                return redirect('reviews:product_detail', data_id)
        else:
            review_form = ReviewForm()
    else:
        return redirect('accounts:basic_login')
    context = {
        'review_form': review_form,
        'product': product,
        'review': selected_review,
        'product_exists': product_exists,
    }
    return render(request, 'reviews/create.html', context)


@login_required
def review_delete(request, review_pk):
    review = Review.objects.get(pk=review_pk)
    if request.user == review.user :
        review.delete()
    return redirect('reviews:index')


@login_required
def review_update(request, review_pk):
    review = Review.objects.get(pk=review_pk)
    if request.user == review.user:
        if request.method == 'POST':
            form = ReviewForm(request.POST, request.FILES, instance=review)
            if form.is_valid():
                form.save()
                review.score = int(request.POST['score'])
                return redirect('reviews:review_detail', review.pk)
        else:
            form = ReviewForm(instance=review)
    else:
        return redirect('reviews:review_detail', review.pk)
    context = {
        'form': form,
        'review': review,
    }
    return render(request, 'reviews/review_update.html', context)


@login_required
def review_like(request, review_pk):
    review = Review.objects.get(pk=review_pk)
    if request.user in review.like_users.all():
        review.like_users.remove(request.user)
        review_is_liked = False
    else:
        review.like_users.add(request.user)
        review_is_liked = True
    context = {
        'review_is_liked': review_is_liked,
        'review_likes_count': review.like_users.count(),
    }
    return JsonResponse(context)


def review_detail(request, review_pk):
    comments = Comment.objects.filter(review=review_pk).order_by('-pk')
    review = Review.objects.get(pk=review_pk)
    context = {
        'review': review,
        'form': CommentForm,
        'comments': comments,
    }
    return render(request, 'reviews/review_detail.html', context)


@login_required
def comment_create(request, review_pk):
    review = Review.objects.get(pk=review_pk)
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.review = review
            comment.save()
            return redirect('reviews:review_detail', review.pk)
        
        else :
            messages.warning(request, "댓글은 빈칸으로 제출하실 수 없습니다.")
            return redirect('reviews:review_detail', review.pk)


@login_required
def comment_like(request, review_pk, comment_pk):
    comment = Comment.objects.get(pk=comment_pk)
    if request.user in comment.like_users.all():
        comment.like_users.remove(request.user)
        comment_is_liked = False
    else:
        comment.like_users.add(request.user)
        comment_is_liked = True
    context = {
        'comment_is_liked': comment_is_liked,
        'review_comment_likes_count': comment.like_users.count(),
    }
    return JsonResponse(context)


@login_required
def comment_delete(request, review_pk, comment_pk):
    comment = Comment.objects.get(pk=comment_pk)
    if request.user == comment.user:
        comment.delete()
    return redirect('reviews:review_detail', review_pk)

