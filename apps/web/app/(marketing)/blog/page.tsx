import {
  getBlogCategories,
  getBlogListingPosts,
  getFeaturedBlogPost,
  type BlogPost,
} from "./posts"
import { BlogPageClient, type BlogCard } from "./blog-page-client"

function toBlogCard(post: BlogPost): BlogCard {
  const {
    slug,
    title,
    excerpt,
    category,
    author,
    displayDate,
    readTime,
    heroImage,
    heroGradient,
    heroAlt,
  } = post
  return {
    slug,
    title,
    excerpt,
    category,
    author,
    displayDate,
    readTime,
    heroImage,
    heroGradient,
    heroAlt,
  }
}

export default function BlogPage() {
  const featuredPost = toBlogCard(getFeaturedBlogPost())
  const listingPosts = getBlogListingPosts().map(toBlogCard)
  const categories = getBlogCategories()

  return (
    <BlogPageClient
      featuredPost={featuredPost}
      listingPosts={listingPosts}
      categories={categories}
    />
  )
}
