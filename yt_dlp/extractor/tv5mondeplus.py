import re
import urllib.parse

from .common import InfoExtractor
from ..utils import (
    determine_ext,
    extract_attributes,
    get_element_html_by_class,
    int_or_none,
    parse_duration,
    traverse_obj,
    try_get,
    url_or_none,
)


class TV5MondePlusIE(InfoExtractor):
    IE_NAME = 'TV5MONDE'
    _VALID_URL = r'https?://(?:www\.)?tv5monde\.com/tv/video/(?P<id>[^/?#]+)'
    _TESTS = [{
        # documentary
        'url': 'https://www.tv5monde.com/tv/video/65931-baudouin-l-heritage-d-un-roi-baudouin-l-heritage-d-un-roi',
        'md5': 'd2a708902d3df230a357c99701aece05',
        'info_dict': {
            'id': '3FPa7JMu21_6D4BA7b',
            'display_id': '65931-baudouin-l-heritage-d-un-roi-baudouin-l-heritage-d-un-roi',
            'ext': 'mp4',
            'title': "Baudouin, l'héritage d'un roi",
            'thumbnail': 'https://psi.tv5monde.com/upsilon-images/960x540/6f/baudouin-f49c6b0e.jpg',
            'duration': 4842,
            'upload_date': '20240130',
            'episode': "Baudouin, l'héritage d'un roi",
            'description': 'md5:78125c74a5cac06d7743a2d09126edad',
        },
    }, {
        # series episode
        'url': 'https://www.tv5monde.com/tv/video/52952-toute-la-vie-mardi-23-mars-2021',
        'md5': 'f5e09637cadd55639c05874e22eb56bf',
        'info_dict': {
            'id': 'obRRZ8m6g9_6D4BA7b',
            'display_id': '52952-toute-la-vie-mardi-23-mars-2021',
            'ext': 'mp4',
            'title': 'Toute la vie',
            'description': 'md5:a824a2e1dfd94cf45fa379a1fb43ce65',
            'thumbnail': 'https://psi.tv5monde.com/media/image/960px/5880553.jpg',
            'duration': 2526,
            'upload_date': '20240411',
            'series': 'Toute la vie',
            'episode': 'Mardi 23 mars 2021',
        },
    }, {
        # movie
        'url': 'https://www.tv5monde.com/tv/video/8771-ce-fleuve-qui-nous-charrie-ce-fleuve-qui-nous-charrie-p001-ce-fleuve-qui-nous-charrie',
        'md5': '87cefc34e10a6bf4f7823cccd7b36eb2',
        'info_dict': {
            'id': 'DOcfvdLKXL_6D4BA7b',
            'display_id': '8771-ce-fleuve-qui-nous-charrie-ce-fleuve-qui-nous-charrie-p001-ce-fleuve-qui-nous-charrie',
            'ext': 'mp4',
            'title': 'Ce fleuve qui nous charrie',
            'description': 'md5:62ba3f875343c7fc4082bdfbbc1be992',
            'thumbnail': 'https://psi.tv5monde.com/media/image/960px/5476617.jpg',
            'duration': 5300,
            'upload_date': '20240411',
            'episode': 'Ce fleuve qui nous charrie',
        },
    }, {
        # news
        'url': 'https://www.tv5monde.com/tv/video/68764-tv5monde-le-journal-edition-du-11-04-24-11h',
        'md5': 'c62977d6d10754a2ecebba70ad370479',
        'info_dict': {
            'id': '0NU1lYMa0Q_6D4BA7b',
            'display_id': '68764-tv5monde-le-journal-edition-du-11-04-24-11h',
            'ext': 'mp4',
            'title': 'TV5MONDE, le journal',
            'description': 'md5:777dc209eaa4423b678477c36b0b04a8',
            'thumbnail': 'https://psi.tv5monde.com/media/image/960px/6183997.jpg',
            'duration': 836,
            'upload_date': '20240411',
            'series': 'TV5MONDE, le journal',
            'episode': 'TV5MONDE, le journal',
        },
    }]
    _GEO_BYPASS = False

    @staticmethod
    def _extract_subtitles(data_captions):
        subtitles = {}
        for f in traverse_obj(data_captions, ('files', lambda _, v: url_or_none(v['file']))):
            subtitles.setdefault(f.get('label') or 'fra', []).append({'url': f['file']})
        return subtitles

    def _real_extract(self, url):
        display_id = self._match_id(url)
        webpage = self._download_webpage(url, display_id)

        if ">Ce programme n'est malheureusement pas disponible pour votre zone géographique.<" in webpage:
            self.raise_geo_restricted(countries=['FR'])

        vpl_data = extract_attributes(self._search_regex(
            r'(<[^>]+class="video_player_loader"[^>]+>)',
            webpage, 'video player loader'))

        video_files = self._parse_json(
            vpl_data['data-broadcast'], display_id)
        formats = []
        video_id = None

        def process_video_files(v):
            nonlocal video_id
            for video_file in v:
                v_url = video_file.get('url')
                if not v_url:
                    continue
                if video_file.get('type') == 'application/deferred':
                    d_param = urllib.parse.quote(v_url)
                    token = video_file.get('token')
                    if not token:
                        continue
                    deferred_json = self._download_json(
                        f'https://api.tv5monde.com/player/asset/{d_param}/resolve?condenseKS=true', display_id,
                        note='Downloading deferred info', headers={'Authorization': f'Bearer {token}'}, fatal=False)
                    v_url = traverse_obj(deferred_json, (0, 'url', {url_or_none}))
                    if not v_url:
                        continue
                    # data-guid from the webpage isn't stable, use the material id from the json urls
                    video_id = self._search_regex(
                        r'materials/([\da-zA-Z]{10}_[\da-fA-F]{7})/', v_url, 'video id', default=None)
                    process_video_files(deferred_json)

                video_format = video_file.get('format') or determine_ext(v_url)
                if video_format == 'm3u8':
                    formats.extend(self._extract_m3u8_formats(
                        v_url, display_id, 'mp4', 'm3u8_native',
                        m3u8_id='hls', fatal=False))
                elif video_format == 'mpd':
                    formats.extend(self._extract_mpd_formats(
                        v_url, display_id, fatal=False))
                else:
                    formats.append({
                        'url': v_url,
                        'format_id': video_format,
                    })

        process_video_files(video_files)

        metadata = self._parse_json(
            vpl_data['data-metadata'], display_id)
        duration = (int_or_none(try_get(metadata, lambda x: x['content']['duration']))
                    or parse_duration(self._html_search_meta('duration', webpage)))

        title = episode = self._html_search_regex(r'<h1 class="main-title">([^<]+)', webpage, 'title', default=None)
        subtitle = self._html_search_regex(r'<p class="video-subtitle">([^<]+)', webpage, 'subtitle', default=None)
        if subtitle:
            episode = subtitle

        ep_summary = get_element_html_by_class('ep-summary', webpage)

        description = self._html_search_regex(
            r'<p class="text">(.+?)</p>', ep_summary,
            'description', fatal=False, flags=re.DOTALL)

        upload_date = self._search_regex(
            r'(?:date_publication|publish_date)["\']\s*:\s*["\'](\d{4}_\d{2}_\d{2})',
            webpage, 'upload date', default=None)
        if upload_date:
            upload_date = upload_date.replace('_', '')

        if not video_id:
            video_id = self._search_regex(
                (r'data-guid=["\']([\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12})',
                 r'id_contenu["\']\s:\s*(\d+)'), webpage, 'video id',
                default=display_id)

        return {
            'id': video_id,
            'display_id': display_id,
            'title': title,
            'description': description,
            'thumbnail': vpl_data.get('data-image'),
            'duration': duration,
            'upload_date': upload_date,
            'formats': formats,
            'subtitles': self._extract_subtitles(self._parse_json(
                traverse_obj(vpl_data, ('data-captions', {str}), default='{}'), display_id, fatal=False)),
            'series': self._html_search_regex(r'<p class="video-title">([^<]+)', webpage, 'title', default=None),
            'episode': episode,
        }
