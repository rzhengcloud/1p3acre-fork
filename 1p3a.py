import os
import sys
import re
import random
import uncurl
import requests


API_HOST = 'api.1point3acres.com'


def do_checkin(headers: dict) -> str:
    with requests.Session() as session:

        # Debugging headers to make sure they're set correctly
        print("Headers being sent:", headers)
        
        with session.get(url=f'https://{API_HOST}/api/users/checkin', headers=headers) as r:
            print("Response from checkin GET:", r.text)  # Check the response content
            emotion = {
                'qdxq': random.choice(r.json()['emotion'])['qdxq'],
                'todaysay': ''.join(chr(random.randint(0x4E00, 0x9FBF)) for _ in range(random.randint(5, 10))),
            }
            print('emotion for today:', emotion)

        with session.post(url=f'https://{API_HOST}/api/users/checkin', headers=headers, json=emotion) as r:
            print("Response from checkin POST:", r.text)  # Check the response content
            return r.json()['msg']


def do_daily_questions(headers: dict) -> str:
    def find_answer_id(question: dict) -> int:
        ans = requests.get(url='https://raw.githubusercontent.com/xjasonlyu/1point3acres/main/questions.json')\
            .json()\
            .get(question['qc'])
        for k, v in question.items():
            if not re.match(r'^a\d$', k):
                continue
            if ans == v:
                return int(k[1])
        return 0

    def compose_ans(question: dict) -> dict:
        return {
            'qid': question['id'],
            'answer': find_answer_id(question),
        }

    with requests.Session() as session:

        with session.get(url=f'https://{API_HOST}/api/daily_questions', headers=headers) as r:
            ans = compose_ans(r.json()['question'])
            if not ans['answer']:
                return '未找到匹配答案，请手动答题'
            print('answer for today:', ans)

        with session.post(url=f'https://{API_HOST}/api/daily_questions', headers=headers, json=ans) as r:
            return r.json()['msg']


def retrieve_headers_from_curl(env: str) -> dict:
    cURL = os.getenv(env, '').replace('\\', ' ')
    return uncurl.parse_context(curl_command=cURL).headers


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
            telegram_send_message(f'{title}\n\n{content}', chat_id, bot_token)


def main(do):

    try:
        headers = retrieve_headers_from_curl('CURL_1P3A')
        headers.update(Host=API_HOST)
        message_text = do(headers)
    except Exception as e:
        message_text = str(e)

    # log to output
    print(message_text)

    # telegram notify
    push_notification(f'1Point3Acres {do.__name__}', message_text)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        # do all
        main(do_checkin)
        main(do_daily_questions)
    elif sys.argv[1] in ('1', 'checkin'):
        main(do_checkin)
    elif sys.argv[1] in ('2', 'question'):
        main(do_daily_questions)
    else:
        print("unknown command")
