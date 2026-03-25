"""web/routers/blog.py — /api/blog/*"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.models import BlogPost
from core.storage import load_blog, save_blog_bg

router = APIRouter()


class BlogPostIn(BaseModel):
    title: str
    tags: list[str] = []
    content: str


class BlogPostPatch(BaseModel):
    title: Optional[str] = None
    tags: Optional[list[str]] = None
    content: Optional[str] = None


@router.get("/api/blog")
def list_blog_posts():
    blog = load_blog()
    return {
        "posts": [
            {**p.model_dump(exclude={"content"}), "preview": p.content[:100]}
            for p in sorted(blog.posts, key=lambda p: p.updated_at, reverse=True)
        ]
    }


@router.get("/api/blog/{post_id}")
def get_blog_post(post_id: str):
    blog = load_blog()
    post = next((p for p in blog.posts if p.id == post_id), None)
    if not post:
        raise HTTPException(404, "ブログ記事が見つかりません")
    return post.model_dump()


@router.post("/api/blog", status_code=201)
def create_blog_post(body: BlogPostIn):
    blog = load_blog()
    post = BlogPost(title=body.title, tags=body.tags, content=body.content)
    blog.posts.append(post)
    save_blog_bg(blog)
    return post.model_dump()


@router.patch("/api/blog/{post_id}")
def update_blog_post(post_id: str, body: BlogPostPatch):
    blog = load_blog()
    post = next((p for p in blog.posts if p.id == post_id), None)
    if not post:
        raise HTTPException(404, "ブログ記事が見つかりません")
    if body.title is not None:
        post.title = body.title
    if body.tags is not None:
        post.tags = body.tags
    if body.content is not None:
        post.content = body.content
    post.updated_at = datetime.now()
    save_blog_bg(blog)
    return post.model_dump()


@router.delete("/api/blog/{post_id}", status_code=204)
def delete_blog_post(post_id: str):
    blog = load_blog()
    idx = next((i for i, p in enumerate(blog.posts) if p.id == post_id), None)
    if idx is None:
        raise HTTPException(404, "ブログ記事が見つかりません")
    blog.posts.pop(idx)
    save_blog_bg(blog)
