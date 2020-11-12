import requests
import json
import argparse
import re
import os
import secrets
import collections
import urllib.parse

_RE_VALID_URL  = re.compile(r'(?:(?:https?://)?hanime.tv/videos/hentai/)?(?P<slug>[a-z\d-]+)')
_RE_VIDEO_ID   = re.compile(r'"hv_id":\s*(?P<id>\d+)[,}]')

_API_VIDEO       = 'https://hw.hanime.tv/api/v8/video'
_API_COMMENTS_L0 = 'https://hr.hanime.tv/api/v8/hthreads'
_API_COMMENTS_L1 = 'https://hr.hanime.tv/api/v8/hthread_comments'
_API_COMMENTS_L2 = 'https://hr.hanime.tv/api/v8/hthread_comment_comments'
_API_USERS       = 'https://members.hanime.tv/rapi/v7/users'

class Hanime:
    def __init__(self, requests_session=None):
        self.session = requests_session or requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; rv:78.0) Gecko/20100101 Firefox/78.0'
        self._totals = None

    def _extract_slug(self, url):
        '''
       Return the video slug part of a URl

        >>> _extract_slug('https://hanime.tv/videos/hentai/sensitive-pornograph-1')
        'sensitive-pornograph-1'
        '''
        match = _RE_VALID_URL.fullmatch(url)
        if match == None:
            raise ValueError(f'Invalid hanime.tv URL: {url}')
        return match.group('slug')

    def _call_api(self, api_url, params):
        '''
        Send a GET request to a hanime.tv API URL
        '''
        hostname = urllib.parse.urlparse(api_url).netloc
        _HEADERS['Host'] = hostname
        headers = {'X-Signature-Version': 'web2',
                   'X-Signature': secrets.token_hex(32)}
        response = self.session.get(api_url, params=params, headers=headers)

        # clear any cookies accrued with that request
        try:
            self.session.cookies.clear(domain=hostname)
        except KeyError:
            pass

        response.raise_for_status()
        return response.json()

    def _get_video(self, url):
        '''
        Return video information from the hanime.tv API
        '''
        video_slug = self._extract_slug(url)
        response = self._call_api(_API_VIDEO, params={'id': video_slug})

        return response['hentai_video']

    def _get_users(self, user_ids):
        users = {}
        params = {'source': 'comments'}
        for i in range(0, len(user_ids), 12):
            params['user_ids[]'] = user_ids[i:i+12]
            for user in self._call_api(_API_USERS, params):
                users[user['id']] = user

        return users

    def _update_totals(self, *, video=None, response=None):
        if response:
            totals = response['meta']['totals']
        else:
            params = {'hv_id': video['id'],
                      'order': 'upvotes,desc',
                      'offset': 0,
                      'count': 1}
            totals = self._call_api(_API_COMMENTS_L0, params)['meta']['totals']

        if self._totals == None:
            self._totals = totals
        else:
            assert self._totals == totals, 'the number of comments changed'

    def _get_all_threads(self, video):
        self._totals = None
        params = {'hv_id': video['id'],
                  'order': 'upvotes,desc',
                  'offset': 0,
                  'count': 0}
        while True:
            response = self._call_api(_API_COMMENTS_L0, params)
            self._update_totals(response=response)

            for thread in response['data']:
                yield thread
                params['offset'] += 1

            if len(response['data']) == 0:
                return

    def _get_all_comment_replies(self, comment):
        if comment['num_replies'] == 0:
            return

        params = {}
        # parent is a level 0 comment (thread)
        if 'hentai_video_id' in comment:
            params['hthread_id'] = comment['id']
            api_url = _API_COMMENTS_L1
        # parent is a level 1 comment (thread reply)
        elif 'hthread_id' in comment:
            params['hthread_comment_id'] = comment['id']
            api_url = _API_COMMENTS_L2
        # parent is a level 2 comment (thread reply reply)
        else:
            assert comment['num_replies'] == 0 # level 2 comments have no replies

        params['order']  = 'upvotes,desc'
        params['offset'] = 0
        params['count']  = 0
        while True:
            response = self._call_api(api_url, params=params)
            for reply in response['data']:
                yield reply
                params['offset'] += 1
            if len(response['data']) == 0:
                return

    def _get_replies(self, parent):
        # parent is a video
        if 'slug' in parent:
            return self._get_all_threads(parent)
        # parent is a comment
        else:
            return self._get_all_comment_replies(parent)

    def _get_comments(self, comments, queue, parent, parent_is_comment=True):
        '''
        Recursively get replies
        Exists so comment threads are flattened depth-first
        '''
        queue.append(parent)
        parent = queue.popleft()

        if parent_is_comment:
            comments.append(parent)

        for reply in self._get_replies(parent):
            self._get_comments(comments, queue, reply)

    def get_comments(self, url, verbose=False):
        '''
        Get all the comments on a hanime.tv video
        Threads are flattened depth first so any comment's replies will directly follow it
        If url and video_id are both provided, video_id overrides url
        '''
        video = self._get_video(url)
        if verbose:
            print('Getting', video['id'])

        comments = []
        queue = collections.deque()
        self._get_comments(comments, queue, video, parent_is_comment=False)

        # make sure the totals haven't changed
        self._update_totals(video=video)
        totals = self._totals
        self._totals = None

        # get user information
        user_ids = sorted({comment['original_poster_user_id'] for comment in comments})
        users = self._get_users(user_ids)

        return {'video': video,
                'comments': {'totals': totals,
                             'comments': comments,
                             'users': users}}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download comments from hanime.tv',
                                     add_help=False,
                                     usage='\b\b\b\b\b\b\bUsage: hanime_comments.py [-h] [-x URL] [-o TEMPLATE] URL [URL ...]',
                                     epilog='Output template keys:\n  video_slug  e.g. sensitive-pornograph-1\n  video_id    e.g. 2714\n\nExample usage:\n  python3 hanime_comments.py https://hanime.tv/video/hentai/sensitive-pornograph-1\n  python3 hanime_comments.py sensitive-pornograph-1',
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser._optionals.title = 'Options'
    parser.add_argument('-h', '--help', help='Show this help message and exit', action='help', default=argparse.SUPPRESS)
    parser.add_argument('-x', '--proxy', metavar='URL', help='URL of the proxy server to use')
    parser.add_argument('-o', '--output',  metavar='TEMPLATE', default='{video_slug}.json', help="Output filename template, default '{video_slug}.json'")
    parser.add_argument('urls', metavar='URL', nargs='+', help=argparse.SUPPRESS)
    args = parser.parse_args()

    session = requests.Session()
    session.proxies = {'http': args.proxy, 'https': args.proxy}

    hanime = Hanime(session)

    for url in args.urls:
        result = hanime.get_comments(url, verbose=True)

        info = {'video_slug': result['video']['slug'],
                'video_id':   result['video']['id']}
        fn = args.output.format(**info)
        directory = os.path.split(fn)[0]
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(fn, 'w') as fp:
             json.dump(result, fp, indent=2, ensure_ascii=False)
