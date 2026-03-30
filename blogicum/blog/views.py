from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, UpdateView

from .forms import CommentForm, PostForm, UserEditForm, UserRegistrationForm
from .models import Category, Comment, Post

POSTS_PER_PAGE = 10


def get_page_obj(queryset, request):
    paginator = Paginator(queryset, POSTS_PER_PAGE)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


def get_published_posts_queryset():
    return (
        Post.objects.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        )
        .select_related('category', 'location', 'author')
        .annotate(comment_count=Count('comments'))
        .order_by('-pub_date')
    )


def index(request):
    page_obj = get_page_obj(get_published_posts_queryset(), request)
    return render(request, 'blog/index.html', {'page_obj': page_obj})


def category_posts(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug, is_published=True)
    post_list = get_published_posts_queryset().filter(category=category)
    page_obj = get_page_obj(post_list, request)
    return render(
        request,
        'blog/category.html',
        {'category': category, 'page_obj': page_obj},
    )


def profile(request, username):
    profile_user = get_object_or_404(Post.author.field.related_model, username=username)
    posts_queryset = (
        Post.objects.filter(author=profile_user)
        .select_related('category', 'location', 'author')
        .annotate(comment_count=Count('comments'))
        .order_by('-pub_date')
    )
    if request.user != profile_user:
        posts_queryset = posts_queryset.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        )
    page_obj = get_page_obj(posts_queryset, request)
    return render(
        request,
        'blog/profile.html',
        {'profile': profile_user, 'page_obj': page_obj},
    )


def get_post_or_404_for_request(request, pk):
    post = get_object_or_404(
        Post.objects.select_related('category', 'location', 'author'),
        pk=pk,
    )
    is_public = (
        post.is_published
        and post.pub_date <= timezone.now()
        and post.category.is_published
    )
    if not is_public and post.author != request.user:
        raise Http404
    return post


def post_detail(request, pk):
    post = get_post_or_404_for_request(request, pk)
    comments = post.comments.select_related('author').order_by('created_at')
    form = CommentForm()
    context = {
        'post': post,
        'comments': comments,
        'form': form,
    }
    return render(request, 'blog/detail.html', context)


class RegistrationView(CreateView):
    form_class = UserRegistrationForm
    template_name = 'registration/registration_form.html'
    success_url = reverse_lazy('login')


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'


@login_required
def create_post(request):
    form = PostForm(request.POST or None, files=request.FILES or None)
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/create.html', {'form': form})


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author != request.user:
        return redirect('blog:post_detail', pk=post_id)
    form = PostForm(request.POST or None, files=request.FILES or None, instance=post)
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', pk=post_id)
    return render(request, 'blog/create.html', {'form': form})


@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author != request.user:
        return redirect('blog:post_detail', pk=post_id)
    form = PostForm(instance=post)
    if request.method == 'POST':
        post.delete()
        return redirect('blog:index')
    return render(request, 'blog/create.html', {'form': form})


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('blog:post_detail', pk=post_id)


@login_required
def edit_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, post_id=post_id)
    if comment.author != request.user:
        return redirect('blog:post_detail', pk=post_id)
    form = CommentForm(request.POST or None, instance=comment)
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', pk=post_id)
    return render(request, 'blog/comment.html', {'form': form, 'comment': comment})


@login_required
def delete_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, post_id=post_id)
    if comment.author != request.user:
        return redirect('blog:post_detail', pk=post_id)
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', pk=post_id)
    return render(request, 'blog/comment.html', {'comment': comment})


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    form_class = UserEditForm
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse('blog:profile', kwargs={'username': self.request.user.username})
