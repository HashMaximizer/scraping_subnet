"""
The MIT License (MIT)
Copyright © 2023 Chris Wilson

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the “Software”), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

# importing necessary libraries and modules

import torch
import datetime
import random
import bittensor as bt
from urllib.parse import urlparse
import os
import re
import html
from neurons.queries import get_query, QueryType, QueryProvider

twitter_query = get_query(QueryType.TWITTER, QueryProvider.TWEET_FLASH)

from itertools import islice

def chunk(it, size):
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())


# Removes links, leading mentions, whitespace, and convert html entities
def text_for_comparison(text):
    # url shorteners can cause problems with tweet verification, so remove urls from the text comparison.
    text = re.sub(r'(https?://)?\S+\.\S+\/?(\S+)?', '', text)
    # Some scrapers put the mentions at the front of the text, remove them.
    text = re.sub(r'^(@\w+\s*)+', '', text)
    # And some trim trailing whitespace at the end of newlines, so ignore whitespace.
    text = re.sub(r'\s+', '', text)
    # And some have special characters escaped as html entities
    return html.unescape(text)



def calculateScore(responses = [], tag = 'tao'):
    """
    This function calculates the score of responses.
    The score is calculated by the degree of similarity between responses, accuracy and time difference.
    Args:
        responses (list): The list of responses.
        tag (str): The tag of responses.
    Returns:
        list: The list of scores for each response.
    """
    if len(responses) == 0:
        return []
    
    # Initialize variables
    # Initialize score list. The length of score list is the same as the length of responses.
    score_list = torch.zeros(len(responses))
    # Initialize time difference list. The length of time difference list is the same as the length of responses.
    time_diff_list = torch.zeros(len(responses))

    correct_score = 0
    max_correct_score = 0
    max_time_diff = 0
    # Initialize accuracy list. The length of accuracy list is the same as the length of responses.
    accuracy_list = torch.zeros(len(responses))
    # Initialize similarity list. The length of similarity list is the same as the length of responses.
    similarity_list = torch.zeros(len(responses))
    max_similar_count = 0
    # Initialize length list. The length score list is the same as the length of responses.
    length_list = torch.zeros(len(responses))
    correct_list = torch.ones(len(responses))
    total_length = 0
    max_length = 0
    relevant_ratio = torch.zeros(len(responses))

    format_score = torch.zeros(len(responses))
    fake_score = torch.zeros(len(responses))
    
    # Count the number of occurrences of each ID
    id_counts = {}
    for i, response in enumerate(responses):

        if response == None:
            responses[i] = []
            response = []
            format_score[i] = 1
        id_list = []
        for tweet in response:
            try:
                # Check that 'text' and 'timestamp' fields exist
                tweet['text'] and tweet['timestamp']
                if tweet['id'] in id_list or tweet['id'] not in tweet['url']:
                    fake_score[i] = 1
                else:
                    id_list.append(tweet['id'])
                
                parsed_url = urlparse(tweet['url'])
                # Extract the path from the URL 
                path = parsed_url.path
                # Get the last component of the path
                last_component = os.path.basename(path)
                if last_component != tweet['id']:
                    bt.logging.info(f"id/url mismatch detected: {tweet['url']}")
                    fake_score[i] = 1

                tweet_id = tweet['id']
                if tweet_id in id_counts:
                    id_counts[tweet_id] += 1
                else:
                    id_counts[tweet_id] = 1
            except Exception as e:
                bt.logging.error(f"❌ Bad format for post: {e}, {tweet}")
                format_score[i] = 1

    # Choose random responses from each miner to compare, and gather their urls
    spot_check_idx = []
    spot_check_urls = []
    spot_check_tweets = []
    for i, response in enumerate(responses):
        if len(response) > 0:
            item_idx = random.randrange(len(response))
            spot_check_idx.append(item_idx)
            url = response[item_idx].get('url')
            if url and re.search("(twitter.com|x.com)\/\w+\/status\/\d+", url):
                spot_check_urls.append(url)
        else:
            spot_check_idx.append(None)

    # Fetch spot check urls
    if len(spot_check_urls) > 0:
        try:
            spot_check_tweets = []
            found_urls = set()
            tries = 0
            remaining_urls = set(spot_check_urls)
            while tries < 5 and len(remaining_urls) > 3:
                urls = random.sample(remaining_urls, k=min(20, len(remaining_urls)))
                bt.logging.info(f"Validating {len(urls)}/{len(remaining_urls)} tweets.")
                batch_tweets = twitter_query.searchByUrl(urls)
                batch_urls = set([tweet['url'] for tweet in batch_tweets])
                bt.logging.info(f"Fetched {len(batch_urls)}/{len(urls)} tweets.")
                remaining_urls = remaining_urls - set(batch_urls)
                spot_check_tweets += batch_tweets
                tries += 1
            found_urls = [tweet['url'] for tweet in spot_check_tweets]
            missing_urls = set(spot_check_urls) - set(found_urls)
            bt.logging.info(f"Missing {len(missing_urls)}/{len(spot_check_urls)} tweets.")
        except Exception as e:
            bt.logging.error(f"❌ Error while verifying post: {e}")

    # Calculate score for each response
    for i, response in enumerate(responses):
        # initialize variables
        similarity_score = 0
        relevant_count = 0
        time_diff_score = 0
        total_length += len(response)
        correct_score = 1
        # calculate max_length
        if len(response) > max_length:
            max_length = len(response)

        # Do spot check for this miner
        correct_score = 0
        if len(response) > 0:
            sample_item = response[spot_check_idx[i]]
            searched_item = next((tweet for tweet in spot_check_tweets if tweet['id'] == sample_item['id']), None)
            if searched_item:
                # Normalize text to account for variations in scraped data.
                miner_text = text_for_comparison(sample_item['text'])
                verify_text = text_for_comparison(searched_item['text'])

                # Some sources truncate time to the nearest minute.
                # timestamp format is '2011-04-25 16:55:15+00:00', so drop the last
                miner_timestamp = sample_item['timestamp'][:16]
                verify_timestamp = searched_item['timestamp'][:16]

                if(verify_text == miner_text and verify_timestamp == miner_timestamp):
                    correct_score = 1
                else:
                    bt.logging.info(f"Tampered tweet! (idx = {i}) {sample_item}")
                    bt.logging.info(f"Original tweet: {searched_item}")
            else: 
                bt.logging.info(f"No result returned for {sample_item} (miner_idx={i})")

        # calculate scores
        for i_item, item in enumerate(response):
            if tag.lower() in item['text'].lower():
                relevant_count += 1
            # calculate similarity score
            similarity_score += (id_counts[item['id']] - 1)
            # calculate time difference score
            date_object = datetime.datetime.strptime(item['timestamp'], '%Y-%m-%d %H:%M:%S+00:00')
            time_diff = datetime.datetime.now() - date_object
            time_diff_score += time_diff.seconds

        if max_similar_count < similarity_score:
            max_similar_count = similarity_score
        if max_time_diff < time_diff_score:
            max_time_diff = time_diff_score
        if max_correct_score < correct_score:
            max_correct_score = correct_score

        similarity_list[i] = similarity_score
        time_diff_list[i] = time_diff_score
        length_list[i] = len(response)
        correct_list[i] = correct_score

        if len(response) > 0:
            relevant_ratio[i] = relevant_count / len(response)
        else:
            relevant_ratio[i] = 0


    similarity_list = (similarity_list + 1) / (max_similar_count + 1)
    time_diff_list = (time_diff_list + 1) / (max_time_diff + 1)
    correct_list = (correct_list + 1) / (max_correct_score + 1)
    length_normalized = (length_list + 1) / (max_length + 1)

    time_diff_contribution = (1 - time_diff_list) * 0.2
    length_contribution = length_normalized * 0.3
    similarity_contribution = (1 - similarity_list) * 0.3
    relevancy_contribution = relevant_ratio * 0.2

    score_list = (similarity_contribution + time_diff_contribution + length_contribution + relevancy_contribution)

    pre_filtered_score = score_list.clone()

    for i, correct_list_item in enumerate(correct_list):
        if correct_list_item < 1:
            score_list[i] = 0
        if format_score[i] == 1:
            score_list[i] = 0
        if fake_score[i] == 1:
            score_list[i] = 0
        if relevant_ratio[i] < 0.5:
            score_list[i] = 0

    for i, response in enumerate(responses):
        if response == [] or response == None:
            score_list[i] = 0
    # normalize score list
            
    filtered_scores = score_list.clone()

    if torch.sum(score_list) == 0:
        normalized_scores = score_list
    else:
        normalized_scores = score_list / torch.sum(score_list)

    scoring_metrics = {
        "correct": correct_list,
        "similarity": similarity_list,
        "time_diff": time_diff_list,
        "time_contrib": time_diff_contribution,
        "length": length_list,
        "length_contrib": length_contribution,
        "similarity_contrib": similarity_contribution,
        "relevancy_contrib": relevancy_contribution,
        "format": format_score,
        "fake": fake_score,
        "pre_filtered_score": pre_filtered_score,
        "filtered_scores": filtered_scores,
        "normalized_scores": normalized_scores,
    }

    return scoring_metrics
        


    

