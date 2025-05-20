import os
import sys
import re
import random
import uncurl
import requests
from collections import OrderedDict
import json # Import json for potential pretty printing if needed

API_HOST = 'api.1point3acres.com'


# --- UPDATED retrieve_headers_and_cookies_from_curl FUNCTION ---
def retrieve_headers_and_cookies_from_curl(env: str) -> tuple[dict, dict]:
    cURL = os.getenv(env, '').replace('\\', ' ') # Replace backslashes for easier parsing
    if not cURL:
        raise ValueError(f"Environment variable {env} is not set or is empty.")

    headers_without_cookie = {}
    cookies = {} # Initialize empty dictionary for manual parsing

    try:
        # --- Use uncurl to parse headers (it seems to work for headers) ---
        # Create a temporary curl string without the -b part so uncurl doesn't try to parse cookies
        # This is a bit tricky - let's instead just use uncurl for all and then manually override cookies if needed
        # Or, let's just do the manual parsing for cookies directly from the original string.

        # Option 1: Use uncurl for headers, manual for cookies (simpler if uncurl headers are good)
        try:
             # Try parsing headers using uncurl first
            context = uncurl.parse_context(curl_command=cURL)
            headers_without_cookie = {
                k: v for k, v in context.headers.items() if k.lower() != 'cookie'
            }
        except Exception as e:
            print(f"Warning: uncurl failed to parse headers, attempting manual header extraction: {e}")
            # Fallback: basic manual header extraction if uncurl fails completely
            # This is a simplified fallback, might not get all headers
            headers_without_cookie = {}
            header_matches = re.findall(r"-H\s+(['\"])(.*?)\1", cURL)
            for match in header_matches:
                 header_content = match.group(2)
                 if ':' in header_content:
                     name, value = header_content.split(':', 1)
                     headers_without_cookie[name.strip()] = value.strip()


        # --- Manual Cookie Extraction ---
        # Regex to find -b followed by space, then quotes (single or double), and capture content inside
        # Handles -b '...' or -b "..."
        cookie_match = re.search(r"-b\s+(['\"])(.*?)\1", cURL)

        if cookie_match:
            raw_cookie_string = cookie_match.group(2) # Group 2 is the content inside the quotes
            # Manually parse the cookie string (key=value; key2=value2)
            # Split by semicolon and optional space
            cookie_pairs = raw_cookie_string.split(';')
            for pair in cookie_pairs:
                # Split each pair by the first equals sign
                if '=' in pair:
                    name, value = pair.split('=', 1)
                    # Strip leading/trailing whitespace from name and value
                    cookies[name.strip()] = value.strip()
                # Handle cookies without values (less common, but possible)
                elif pair.strip():
                    cookies[pair.strip()] = ''

        # --- End Manual Cookie Extraction ---


        # Ensure essential headers are present
        if 'Host' not in headers_without_cookie and 'host' not in headers_without_cookie:
             headers_without_cookie['Host'] = API_HOST
        if 'User-Agent' not in headers_without_cookie and 'user-agent' not in headers_without_cookie:
             # Use a default User-Agent if not found
             headers_without_cookie['User-Agent'] = 'Mozilla/5.0 (compatible; MyScript/1.0)'


        return headers_without_cookie, cookies

    except Exception as e:
        # Catch any errors during the manual parsing as well
        print(f"Critical Error during header/cookie extraction from {env}: {e}")
        # Re-raise to ensure the main function catches it and reports failure
        raise


# --- The rest of your gem.py script remains the same ---
# ... (do_checkin, do_daily_questions, push_notification, main, __main__)
# Keep the print("Raw cookies dictionary from retrieve_headers_and_cookies_from_curl:", cookies)
# in the main function for now, as it will show if the manual parsing worked.
# Keep the print("Cookies loaded into session with explicit domain:", list(session.cookies))
# in do_checkin/do_daily_questions as well.

# --- do_checkin remains the same (with the explicit domain logic) ---
def do_checkin(headers: dict, cookies: dict) -> str:
    with requests.Session() as session:
        api_domain = API_HOST
        jar = requests.cookies.RequestsCookieJar()
        for name, value in cookies.items():
             jar.set(name, value, domain=api_domain)
        session.cookies.update(jar)

        # Debugging print to show what was loaded into the session
        print("Cookies loaded into session with explicit domain:", list(session.cookies))


        with session.get(url=f'https://{API_HOST}/api/users/checkin', headers=headers) as r:
            print("Response from checkin GET:", r.text)
            r.raise_for_status()

            response_json = r.json()

            if response_json.get("errno") == -1:
                 return response_json.get("msg", "Checkin GET failed (login required?)")

            emotion_options = response_json.get('emotion', [])
            if not emotion_options:
                 return "Checkin GET response missing emotion data."

            emotion = {
                'qdxq': random.choice(emotion_options)['qdxq'],
                'todaysay': ''.join(chr(random.randint(0x4E00, 0x9FBF)) for _ in range(random.randint(5, 10))),
            }
            print('emotion for today:', emotion)

        with session.post(url=f'https://{API_HOST}/api/users/checkin', headers=headers, json=emotion) as r:
            print("Response from checkin POST:", r.text)
            r.raise_for_status()
            post_response_json = r.json()
            return post_response_json.get('msg', "Checkin POST response missing 'msg'")


# --- do_daily_questions remains the same (with the explicit domain logic) ---
def do_daily_questions(headers: dict, cookies: dict) -> str:
    def find_answer_id(question: dict) -> int:
        try:
            ans_req = requests.get(url='https://raw.githubusercontent.com/xjasonlyu/1point3acres/main/questions.json')
            ans_req.raise_for_status()
            answer_map = ans_req.json()
        except Exception as e:
             print(f"Error fetching or parsing questions.json: {e}")
             return 0

        expected_ans = answer_map.get(question.get('qc', ''), None)
        if expected_ans is None:
             print(f"Warning: No answer found in questions.json for question: {question.get('qc', 'N/A')}")
             return 0

        for k, v in question.items():
            if not re.match(r'^a\d+$', k):
                continue
            if not isinstance(v, str):
                 continue

            cleaned_v = re.sub(r'\{hide=?\d*\}(.*?)\{/hide\}|\[hide=?\d*\](.*?)\[\\hide\]', r'\1\2', v, flags=re.IGNORECASE)
            cleaned_v = cleaned_v.strip()

            if expected_ans.strip() == cleaned_v:
                 try:
                     return int(k[1:])
                 except ValueError:
                     print(f"Warning: Could not parse answer key number: {k}")
                     return 0

        print(f"Warning: Found external answer '{expected_ans}' but could not match it to API options for question: {question.get('qc', 'N/A')}")
        return 0


    def compose_ans(question: dict) -> dict:
        return {
            'qid': question.get('id', None),
            'answer': find_answer_id(question),
        }

    with requests.Session() as session:
        api_domain = API_HOST
        jar = requests.cookies.RequestsCookieJar()
        for name, value in cookies.items():
             jar.set(name, value, domain=api_domain)
        session.cookies.update(jar)

        # Debugging print to show what was loaded into the session
        print("Cookies loaded into session with explicit domain:", list(session.cookies))


        with session.get(url=f'https://{API_HOST}/api/daily_questions', headers=headers) as r:
            print("Response from daily_questions GET:", r.text)
            r.raise_for_status()

            response_json = r.json()

            if response_json.get("errno") == -1:
                 return response_json.get("msg", "Daily Questions GET failed (login required?)")

            question = response_json.get('question')
            if not question:
                 return "Daily Questions GET response missing 'question' data."

            ans = compose_ans(question)

            if ans.get('answer') is None or ans['answer'] == 0:
                 return f'未找到匹配答案，请手动答题 (Question: {question.get("qc", "N/A")})'

            if ans.get('qid') is None:
                 return "Could not find question ID (qid) in the response."

            print('answer for today:', ans)

        with session.post(url=f'https://{API_HOST}/api/daily_questions', headers=headers, json=ans) as r:
            print("Response from daily_questions POST:", r.text)
            r.raise_for_status()
            post_response_json = r.json()
            return post_response_json.get('msg', "Daily Questions POST response missing 'msg'")


# --- Remainder of script is the same ---
def push_notification(title: str, content: str) -> None:

    def telegram_send_message(text: str, chat_id: str, token: str, silent: bool = False) -> None:
        with requests.post(url=f'https://api.telegram.org/bot{token}/sendMessage',
                           json={
                               'chat_id': chat_id,
                               'text': text,
                               'disable_notification': silent,
                               'disable_web_page_preview': True,
                           }) as r:
            r.raise_for_status()

    try:
        from notify import telegram_bot
        telegram_bot(title, content)
    except ImportError:
        chat_id = os.getenv('TG_USER_ID')
        bot_token = os.getenv('TG_BOT_TOKEN')
        if chat_id and bot_token:
            try:
                telegram_send_message(f'{title}\n\n{content}', chat_id, bot_token)
            except Exception as e:
                 print(f"Error sending Telegram notification: {e}")
        else:
            print("Telegram environment variables (TG_USER_ID, TG_BOT_TOKEN) not set. Skipping notification.")
    except Exception as e:
         print(f"Error during notification attempt: {e}")

def main(do_function):
    message_text = "Task did not complete."
    title = f'1Point3Acres {do_function.__name__}'

    try:
        headers, cookies = retrieve_headers_and_cookies_from_curl('CURL_1P3A')
        # --- NEW DEBUG PRINT LINE ---
        print("Raw cookies dictionary from retrieve_headers_and_cookies_from_curl:", cookies)
        # ----------------------------
        message_text = do_function(headers, cookies)

        print(message_text)

        success_keywords = ["OK", "成功", "已签到", "已答题"]
        failure_keywords = ["登录", "失败", "错误", "error", "exception", "找不到匹配答案", "missing"]

        is_success = any(kw in message_text for kw in success_keywords)
        is_failure = any(kw in message_text.lower() for kw in failure_keywords)


        if is_success and not is_failure:
             push_notification(f'{title} Success', message_text)
        else:
             push_notification(f'{title} Failed', message_text)

    except ValueError as ve:
        message_text = f"Configuration Error: {ve}"
        print(message_text)
        push_notification(f'{title} Failed', message_text)
    except requests.exceptions.RequestException as re:
        message_text = f"Network/HTTP Error: {re}"
        print(message_text)
        push_notification(f'{title} Failed', message_text)
    except Exception as e:
        message_text = f"An unexpected error occurred: {e}"
        print(message_text)
        push_notification(f'{title} Failed', message_text)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("--- Running Checkin ---")
        main(do_checkin)
        print("\n--- Running Daily Questions ---")
        main(do_daily_questions)
    elif sys.argv[1] in ('1', 'checkin'):
        print("--- Running Checkin ---")
        main(do_checkin)
    elif sys.argv[1] in ('2', 'question'):
         print("\n--- Running Daily Questions ---")
         main(do_daily_questions)
    else:
        print("unknown command")