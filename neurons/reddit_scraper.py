import praw
import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
import bittensor as bt

load_dotenv()
r_client = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT")
)

def convert_utc_timestamp_to_iso8601(timestamp_seconds):
    # Convert timestamp to datetime object
    dt_utc = datetime.utcfromtimestamp(timestamp_seconds).replace(tzinfo=timezone.utc)

    # Format datetime object in ISO 8601 format
    iso8601_format = dt_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    return iso8601_format

def map_results(results: list):
    ret = [{
        'id': f"t3_{item.id}",
        'url': item.url,
        'title': item.title,
        'text': item.selftext,
        'likes': item.score,
        'dataType' : 'post',
        'community' : item.subreddit.name,
        'username' : item.author.name,
        'parent' : None,
        'timestamp' : convert_utc_timestamp_to_iso8601(int(item.created_utc))
    } for item in results]

    return ret

def execute(client : praw.Reddit = r_client, query : list = None, timeout : float = 30.0, max_res : int = 20, max_posts : int = 20, max_comments : int = 10):
    print("testing...")

    # max_res = 1000
    res = 0
    posts = 0
    start = time.time()
    results = []

    for post in client.subreddit("all").search(query=query[0], sort="new", limit=max_posts):
        if res >= max_res: break
        if posts >= max_posts: break
        if time.time() - start >= timeout: break

        num = 0
        # for comment in post.comments:
        #     if num >= max_comments: break
        #     elif query.lower() in comment.body.lower():
        #         results.append(comment)
        #         num += 1
        #         res += 1

        if query[0].lower() in post.title.lower():
            results.append(post)
            posts += 1
            res += 1
        # print(f"---=== {submission.title} ===---")
        # print(f"written by: {submission.author}")
        if time.time() - start >= timeout: break

    end = time.time()
    bt.logging.debug(f"SCRAPED IN: {end - start}s")
    bt.logging.debug(f"NUMBER OF RESULTS: {len(results)}")

    return map_results(results)

if __name__ == "__main__":
    res = execute(client=r_client, query=["btc"], max_res=500, max_posts=500)
    print(res[0])
