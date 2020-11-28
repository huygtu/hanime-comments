# hanime-comments
Get comments from hanime.tv

Requests are sometimes blocked by Cloudflare but this happens unpredictably so I haven't been able to circumvent it. In the future I might use selenium or something to get around it.

### Requirements
* `Python 3.6` at least (because it uses [secrets](https://docs.python.org/3/library/secrets.html))
* `python-requests`

### Usage
`python3 hanime_comments.py [-h] [-x URL] [-o TEMPLATE] URL [URL ...]`

#### Options
* `-h`, `--help` Help
* `-x`, `--proxy` URL of the proxy server to use
* `-o`, `--output` Output filename template, default `'{video_slug}.json'`

#### Output template keys
* `video_slug`,  e.g. `'sensitive-pornograph-1'`
* `video_id`, e.g. `2714`

#### Example usage
* `python3 hanime_comments.py https://hanime.tv/videos/hentai/sensitive-pornograph-1`
* `python3 hanime_comments.py sensitive-pornograph-1`

### Output
Output is JSON and looks like this:
```
{
  "video": {..},
  "comments": {
    "totals": {
      "num_threads": ..,
      "num_comments": ..,
    },
    "comments": [..],
    "users": {..}
  }
}
```
[There's an example of this in the repo.](example.json)

`num_threads` is the number of top-level comments and in my tests it's always been accurate. `num_comments` is purportedly the number of comments but in my tests the number of comments that you can see is always smaller (even on the website).

For example these are the numbers for https://hanime.tv/videos/hentai/sensitive-pornograph-1 on 2020-11-11:
```
>>> c = result['comments']
>>> c['totals']
{'num_threads': 150, 'num_comments': 241}
>>> len(c['comments'])
238
>>> len(only_top_level_comments(c['comments']))
150
```
Not really sure what's going on here, but it matches what you get on the website so it's fine I guess.

### Usage within Python
```
import requests
import hanime_comments

session = requests.session()
hanime = hanime_comments.Hanime(session)

comments = hanime.get_comments('https://hanime.tv/videos/hentai/sensitive-pornograph-1')
```

### To do
* More explanatory comments
* Progress bar
* Option to download in most recent order
