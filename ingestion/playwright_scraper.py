import sys, hashlib, time, json
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

def scrape_ios_reviews(days_back: int = 84) -> list[dict]:
    """Scrape Groww iOS App Store reviews using Playwright."""
    reviews = []
    cutoff = datetime.now() - timedelta(days=days_back)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                      "Version/17.0 Mobile/15E148 Safari/604.1",
            viewport={"width": 375, "height": 667}
        )
        
        try:
            page = context.new_page()
            page.goto('https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703')
            
            # Wait for page to load
            page.wait_for_load_state('networkidle')
            
            # Look for reviews section and scroll to load more
            max_scrolls = 10
            for scroll_attempt in range(max_scrolls):
                try:
                    # Look for review elements
                    review_elements = page.query_selector_all('[data-test-below-the-fold*="review"], .we-customer-review, .review')
                    
                    if not review_elements:
                        # Try alternative selectors
                        review_elements = page.query_selector_all('[data-test-below-the-fold="review"], .we-customer-review')
                    
                    if len(review_elements) >= 50:  # Got enough reviews
                        break
                        
                    # Scroll down to load more reviews
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"Scroll attempt {scroll_attempt + 1} failed: {e}")
                    break
            
            # Extract reviews
            review_elements = page.query_selector_all('[data-test-below-the-fold*="review"], .we-customer-review, .review')
            
            for i, element in enumerate(review_elements[:200]):  # Limit to 200 reviews
                try:
                    # Extract rating
                    rating_elem = element.query_selector('[aria-label*="stars"], .we-star-rating, [data-test-rating]')
                    rating = 5  # default
                    if rating_elem:
                        rating_text = rating_elem.get_attribute('aria-label') or rating_elem.text_content()
                        if 'stars' in rating_text.lower():
                            rating = int(rating_text.lower().split('stars')[0].split()[-1])
                        elif rating_text.strip().isdigit():
                            rating = int(rating_text.strip())
                    
                    # Extract title
                    title_elem = element.query_selector('h3, .we-customer-review__title, [data-test-review-title]')
                    title = title_elem.text_content().strip() if title_elem else ''
                    
                    # Extract content
                    content_elem = element.query_selector('p, .we-customer-review__body, [data-test-review-body]')
                    content = content_elem.text_content().strip() if content_elem else ''
                    
                    # Extract date
                    date_elem = element.query_selector('time, .we-customer-review__date, [data-test-review-date]')
                    date_str = ''
                    if date_elem:
                        date_text = date_elem.get_attribute('datetime') or date_elem.text_content()
                        if date_text:
                            try:
                                if 'T' in date_text:
                                    review_date = datetime.fromisoformat(date_text.replace('Z', '+00:00'))
                                else:
                                    # Try to parse various date formats
                                    for fmt in ['%Y-%m-%d', '%d %b %Y', '%b %d, %Y']:
                                        try:
                                            review_date = datetime.strptime(date_text.strip(), fmt)
                                            break
                                        except ValueError:
                                            continue
                                    else:
                                        review_date = datetime.now()
                                date_str = review_date.strftime('%Y-%m-%d')
                            except:
                                date_str = datetime.now().strftime('%Y-%m-%d')
                    
                    # Skip if no content or too old
                    if not content or len(content) < 10:
                        continue
                    
                    if date_str:
                        try:
                            review_date = datetime.strptime(date_str, '%Y-%m-%d')
                            if review_date < cutoff:
                                continue
                        except:
                            pass
                    
                    # Create review object
                    review_id = hashlib.sha256(f"ios_{content[:50]}_{date_str}".encode()).hexdigest()
                    
                    reviews.append({
                        'review_id': review_id,
                        'store': 'ios',
                        'rating': rating,
                        'title': title,
                        'text': content,
                        'date': date_str or datetime.now().strftime('%Y-%m-%d'),
                        'app_version': '',
                        'raw_id': f"ios_{i}",
                        'language_detected': 'en',
                        'language_confidence': 0.99,
                        'pii_stripped': True,
                        'is_duplicate': False,
                        'suspicious_review': False,
                    })
                    
                except Exception as e:
                    print(f"Error extracting iOS review {i}: {e}")
                    continue
            
        except Exception as e:
            print(f"iOS scraping error: {e}")
        finally:
            browser.close()
    
    print(f"iOS scraping completed: {len(reviews)} reviews found")
    return reviews

def scrape_android_reviews(days_back: int = 84) -> list[dict]:
    """Scrape Groww Android Play Store reviews using Playwright."""
    reviews = []
    cutoff = datetime.now() - timedelta(days=days_back)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            viewport={"width": 360, "height": 640}
        )
        
        try:
            page = context.new_page()
            page.goto('https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en&gl=in')
            
            # Wait for page to load
            page.wait_for_load_state('networkidle')
            
            # Click on "See all reviews" if present
            try:
                see_all_btn = page.query_selector('[aria-label*="See all reviews"], button:has-text("See all reviews")')
                if see_all_btn:
                    see_all_btn.click()
                    page.wait_for_load_state('networkidle')
            except:
                pass
            
            # Scroll to load more reviews
            max_scrolls = 15
            for scroll_attempt in range(max_scrolls):
                try:
                    # Look for review elements
                    review_elements = page.query_selector_all('[role="listitem"] .RCK1c, .d15Mdf, .bAhLNe')
                    
                    if len(review_elements) >= 100:  # Got enough reviews
                        break
                        
                    # Scroll down to load more reviews
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    time.sleep(2)
                    
                    # Look for "Show more" or "Load more" buttons
                    load_more_btn = page.query_selector('[aria-label*="Load more"], [aria-label*="Show more"], button:has-text("Load more")')
                    if load_more_btn:
                        load_more_btn.click()
                        time.sleep(2)
                        
                except Exception as e:
                    print(f"Scroll attempt {scroll_attempt + 1} failed: {e}")
                    break
            
            # Extract reviews
            review_elements = page.query_selector_all('[role="listitem"] .RCK1c, .d15Mdf, .bAhLNe')
            
            for i, element in enumerate(review_elements[:200]):  # Limit to 200 reviews
                try:
                    # Extract rating
                    rating_elem = element.query_selector('[aria-label*="stars"], .jUL89d, .nt2C1d')
                    rating = 5  # default
                    if rating_elem:
                        rating_text = rating_elem.get_attribute('aria-label') or ''
                        if 'stars' in rating_text.lower():
                            rating = int(rating_text.lower().split('stars')[0].split()[-1])
                    
                    # Extract content
                    content_elem = element.query_selector('.h3YV2d, .bNv7P, .X43Pjb')
                    content = content_elem.text_content().strip() if content_elem else ''
                    
                    # Extract date
                    date_elem = element.query_selector('.bp9Aid, .LiK2Gb, .pM2G0')
                    date_str = ''
                    if date_elem:
                        date_text = date_elem.text_content().strip()
                        if date_text:
                            try:
                                # Parse various date formats
                                if 'ago' in date_text.lower():
                                    # Handle "X days ago" format
                                    if 'day' in date_text.lower():
                                        days = int(date_text.lower().split('day')[0].split()[-1])
                                        review_date = datetime.now() - timedelta(days=days)
                                    elif 'week' in date_text.lower():
                                        weeks = int(date_text.lower().split('week')[0].split()[-1])
                                        review_date = datetime.now() - timedelta(weeks=weeks)
                                    elif 'month' in date_text.lower():
                                        months = int(date_text.lower().split('month')[0].split()[-1])
                                        review_date = datetime.now() - timedelta(days=months*30)
                                    else:
                                        review_date = datetime.now()
                                else:
                                    # Try standard date formats
                                    for fmt in ['%Y-%m-%d', '%d %b %Y', '%b %d, %Y']:
                                        try:
                                            review_date = datetime.strptime(date_text.strip(), fmt)
                                            break
                                        except ValueError:
                                            continue
                                    else:
                                        review_date = datetime.now()
                                
                                date_str = review_date.strftime('%Y-%m-%d')
                            except:
                                date_str = datetime.now().strftime('%Y-%m-%d')
                    
                    # Skip if no content or too old
                    if not content or len(content) < 10:
                        continue
                    
                    if date_str:
                        try:
                            review_date = datetime.strptime(date_str, '%Y-%m-%d')
                            if review_date < cutoff:
                                continue
                        except:
                            pass
                    
                    # Create review object
                    review_id = hashlib.sha256(f"android_{content[:50]}_{date_str}".encode()).hexdigest()
                    
                    reviews.append({
                        'review_id': review_id,
                        'store': 'android',
                        'rating': rating,
                        'title': '',
                        'text': content,
                        'date': date_str or datetime.now().strftime('%Y-%m-%d'),
                        'app_version': '',
                        'raw_id': f"android_{i}",
                        'language_detected': 'en',
                        'language_confidence': 0.99,
                        'pii_stripped': True,
                        'is_duplicate': False,
                        'suspicious_review': False,
                    })
                    
                except Exception as e:
                    print(f"Error extracting Android review {i}: {e}")
                    continue
            
        except Exception as e:
            print(f"Android scraping error: {e}")
        finally:
            browser.close()
    
    print(f"Android scraping completed: {len(reviews)} reviews found")
    return reviews

def scrape_all_reviews(days_back: int = 84) -> dict:
    """Scrape reviews from both iOS and Android stores."""
    print("Starting Playwright-based review scraping...")
    
    # Scrape iOS reviews
    print("Fetching iOS reviews...")
    ios_reviews = scrape_ios_reviews(days_back)
    
    # Scrape Android reviews
    print("Fetching Android reviews...")
    android_reviews = scrape_android_reviews(days_back)
    
    all_reviews = ios_reviews + android_reviews
    
    result = {
        'ios_reviews': ios_reviews,
        'android_reviews': android_reviews,
        'total_reviews': all_reviews,
        'ios_count': len(ios_reviews),
        'android_count': len(android_reviews),
        'total_count': len(all_reviews),
        'scraping_method': 'playwright',
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"Scraping completed: {len(ios_reviews)} iOS + {len(android_reviews)} Android = {len(all_reviews)} total")
    
    # Show sample reviews
    if ios_reviews:
        sample = ios_reviews[0]
        print(f"iOS sample: [{sample['rating']}★] {sample['text'][:80]}")
    
    if android_reviews:
        sample = android_reviews[0]
        print(f"Android sample: [{sample['rating']}★] {sample['text'][:80]}")
    
    return result

if __name__ == "__main__":
    # Test the scraper
    print("Testing Playwright scraper...")
    result = scrape_all_reviews(days_back=30)  # Test with last 30 days
    
    print(f"\nResults:")
    print(f"iOS: {result['ios_count']} reviews")
    print(f"Android: {result['android_count']} reviews")
    print(f"Total: {result['total_count']} reviews")
    
    # Save sample results
    output_file = Path("data/playwright_test_results.json")
    output_file.parent.mkdir(exist_ok=True)
    
    # Convert datetime objects to strings for JSON serialization
    serializable_result = result.copy()
    serializable_result['total_reviews'] = [
        {k: v for k, v in review.items() if k != 'language_confidence'} 
        for review in result['total_reviews'][:10]  # Save only first 10 for testing
    ]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_result, f, indent=2, ensure_ascii=False)
    
    print(f"Sample results saved to: {output_file}")
