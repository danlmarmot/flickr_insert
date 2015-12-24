# -*- coding: utf-8 -*-
"""
Inserts a Flickr image in a Pelican article

"""
import logging
import re
import configparser
import csv
import time
import random
import copy
from itertools import chain
import flickrapi
from flickrapi import shorturl
from pelican import signals, ArticlesGenerator, PagesGenerator
from jinja2 import Template

# Load settings
plugin_settings = {
    'FLICKR_INSERT_API_KEY': {
        'required': True,
    },
    'FLICKR_INSERT_API_SECRET': {
        'required': True,
    },
    'FLICKR_INSERT_IMAGE_SIZE': {
        'required': False,
        'default': 'Medium 640'
    },
    'FLICKR_INSERT_CACHE_CFG': {
        'required': False,
        'default': {
            "filename":
                "flickr_insert_cache.csv",
            "key_field":
                "pic_id",  # cache key field
            "increment":
                86400,  # 1 day, in seconds
            "session_interval":
                int(3600),  # always use cache when time since
            # last update is less than this
            "recent_interval":
                int(3 * 86400),  # 3 days, always check for changes
            "refresh_interval":
                int(14 * 86400),  # 14 days, for intermittent refreshes
            "field_names":  # cache file columns
                ["title", "insert_image_url_base",
                 "last_updated", "next_update",
                 "last_updated_str", "next_update_str",
                 "flickr_error"]
        }
    }
}


def get_cache_cfg():
    return plugin_settings['FLICKR_INSERT_CACHE_CFG']


# This produces two matches: one for the whole tag,
#  one for all the parameters after, such as url= or id=
FLICKR_REGEX = re.compile(r'<p>\s*(\[flickr:(.*)\])\s*</p>', re.IGNORECASE)

BOOLEAN_STATES = {
    '1': True, 'yes': True, 'y': True, 'true': True, 'on': True,
    '0': False, 'no': False, 'n': False, 'false': False, 'off': False}


# Returns a list of regex matches
def get_flickr_tags(content):
    tags = []

    matches = FLICKR_REGEX.findall(content)
    params = {}

    for m in matches:
        config = configparser.ConfigParser()
        config.read_string(u"[temp]\n" + m[1].replace(",", "\n"))
        params = {item[0]: item[1] for item in config.items('temp')}
        params['full_tag'] = m[0]

    tags.append(params)

    return tags


def parse_flickr_tag(tag_str):
    tag_params = {}

    cp_temp = configparser.ConfigParser()
    cp_temp.read_string("[temp]\n" + tag_str.replace(",", "\n"))
    read_params = {item[0]: item[1] for item in cp_temp.items('temp')}

    tag_params.update(read_params)

    return tag_params


# if the parameter float is not supplied, the image will be full-width
DEFAULT_TEMPLATE = """<div class="caption-container">
    <a class="caption" href="{{url}}" target="_blank">
    <div class="image-wrapper{% if float %} pull-{{float}}{%endif%}">
        <img src="{{insert_image_url}}"
            alt="{{title}}"
            title="{{title}}"
            class="img-polaroid"
            {% if FLICKR_TAG_INCLUDE_DIMENSIONS %}
                width="{{width}}"
                height="{{height}}"
            {% endif %} />
        {% if show_caption %}
        <div class="desc">
            <p class="desc_content">{{title}}</p>
        </div>
        {% endif %}
    </div>
    </a>
</div>
{% if not float %}
<div class="clearfix"></div>
{% endif %}
"""

# Additional definitions described at
#  https://www.flickr.com/services/api/misc.urls.html
DEFAULT_PHOTO_SUFFIX = "z"
photo_suffix_sizes = {
    "s": ["smallsq", "sq75", "75"],
    "t": ["thumb", "th100", "100"],
    "q": ["largesq", "sq150", "150"],
    "m": ["small", "small240", "240"],
    DEFAULT_PHOTO_SUFFIX: ["medium", "medium640", "640"],
    "b": ["large", "large1024", "1024"],
}
# make a dictionary
photo_suffixes = {size: letter
                  for letter, sizes in photo_suffix_sizes.items()
                  for size in sizes}

# When captions are shown or not--for smaller sizes,
#  they are not shown by default (override with caption=true)
photo_captions_enabled = {
    False: ["s", "t", "q", "m"],
    True: ["z", "b"]
}
caption_for_size = {letter: caption
                    for caption, letters in photo_captions_enabled.items()
                    for letter in letters}

logger = logging.getLogger(__name__)


def init_flickr_insert(generator):
    for setting_name, setting_value in plugin_settings.items():
        try:
            generator.settings[setting_name]
        except KeyError:
            if setting_value['required']:
                raise Exception('Missing required setting: ' + setting_name)
            generator.settings.setdefault(setting_name,
                                          setting_value['default'])

    # Add context settings for this particular invocation
    # Create the flickr 'connection'
    flickr_conn = flickrapi.FlickrAPI(
        generator.context.get('FLICKR_INSERT_API_KEY'),
        generator.context.get('FLICKR_INSERT_API_SECRET'))
    flicker_insert_ctx = {"flickr_conn": flickr_conn}
    generator.context.update({'flickr_insert_ctx': flicker_insert_ctx})

    # Get current time in epoch seconds
    flicker_insert_ctx.update({"cur_time": int(time.time())})

    # Get the article template
    template_name = generator.context.get('FLICKR_INSERT_TEMPLATE_NAME')
    if template_name is not None:
        try:
            template = generator.get_template(template_name)
        except Exception:
            logger.error('[flickr_insert]:'
                         ' Unable to get custom template %s'
                         % template_name)
            template = Template(DEFAULT_TEMPLATE)
    else:
        template = Template(DEFAULT_TEMPLATE)

    flicker_insert_ctx.update({"template": template})

    # add cache_config from settings to context
    cache_cfg = generator.settings.get('FLICKR_INSERT_CACHE_CFG')
    flicker_insert_ctx.update({"cache_cfg": cache_cfg})
    flicker_insert_ctx.update({"key_field": cache_cfg['key_field']})

    cache_loader = load_cache_from_csv
    cache = cache_loader(cache_cfg['filename'],
                         key_name=cache_cfg['key_field'])

    flicker_insert_ctx.update({"cache": cache})

    return


def get_photo_id_and_url(photo_dict, id_field="id"):
    pic_id = photo_dict.get(id_field, photo_dict.get('id', None))

    output = {id_field: pic_id}
    output.update({"url": photo_dict.get("url", None)})

    if not output['url']:
        output['url'] = "https://flic.kr/p/" + \
                        shorturl.encode(pic_id)

    elif not output[id_field]:
        short_url_id = photo_dict['url'].strip("/").split("/")[-1]
        output[id_field] = shorturl.decode(short_id=short_url_id)

    output['url'] = output['url'].replace("http://", "https://")
    return output


# Ensure image size is correctly speled and has correct Flickr suffix
def ensure_photo_size(photo, default_image_size="medium"):
    size_dict = dict()

    if photo.get('size', "") not in photo_suffixes.keys():
        size_dict['size'] = default_image_size
    else:
        size_dict['size'] = photo['size']

    # Get URL size_suffix for image size
    size_dict['size_suffix'] = photo_suffixes.get(size_dict['size'])

    return size_dict


# If caption is not already defined, set it with the default,
#  else tidy up the caption parameter
def ensure_photo_show_caption(photo):
    output = dict()

    # Caption can be specified with 'show_caption' or 'caption'
    specified_caption = photo.get('caption',
                                  photo.get('show_caption', False))

    if specified_caption:
        output['show_caption'] = \
            BOOLEAN_STATES.get(specified_caption.lower(), True)
    else:
        output['show_caption'] = \
            caption_for_size[photo.get('size_suffix', DEFAULT_PHOTO_SUFFIX)]

    return output


# Combines two fields
# Needs to be run after a successful Flickr API call or cache hit
def ensure_photo_insert_image_url(photo):
    output = dict()
    output['insert_image_url'] = \
        photo.get("insert_image_url_base", "") + \
        photo.get("size_suffix", DEFAULT_PHOTO_SUFFIX) + ".jpg"

    return output


# "float" the image left or right;
#  "float" applies a 'pull-right' or 'pull-left' class to the image
# The pull-left/pull-right classes are pre-defined in Bootstrap3
def ensure_photo_float(photo):
    output = dict()

    p_float = photo.get('float', '').lower()
    if p_float not in ["left", "right"]:
        output['float'] = ''
    else:
        output['float'] = p_float

    return output


def replace_document_tags(generator):
    # Setup cache
    cache_cfg = generator.settings.get('FLICKR_INSERT_CACHE_CFG')
    key_field = cache_cfg['key_field']
    cache_loader = load_cache_from_csv
    cache_saver = save_cache_to_csv
    cache = cache_loader(cache_cfg['filename'], key_name=key_field)

    logger.info('[flickr_insert]: Looking for flickr tags in content')

    # For articles and draft articles
    if isinstance(generator, ArticlesGenerator):
        for document in chain(generator.articles, generator.drafts):
            replace_tags_in_document(document, generator, cache)

    # For pages
    if isinstance(generator, PagesGenerator):
        for document in chain(generator.pages, generator.hidden_pages):
            replace_tags_in_document(document, generator, cache)

    # Save away cache
    cache_saver(cache, filename=cache_cfg['filename'],
                fieldnames=cache_cfg['field_names'], key_name=key_field)


def replace_tags_in_document(document, generator, cache):
    # Note that cache is modified in this function with any updates

    flickr_ctx = generator.context.get('flickr_insert_ctx', None)
    if not flickr_ctx:
        return

    cache_cfg = flickr_ctx['cache_cfg']
    key_field = cache_cfg['key_field']
    # cache = flickr_ctx['cache']

    for match in FLICKR_REGEX.findall(document._content):

        # Gather and clean [flickr:] tag from article content
        photo = parse_flickr_tag(match[1])
        photo.update(get_photo_id_and_url(photo, id_field=key_field))
        photo.update(ensure_photo_size(photo))
        photo.update(ensure_photo_show_caption(photo))
        photo.update(ensure_photo_float(photo))

        # Ensure there's a cache entry before calling update
        # Cache entries look like {"A", {"pic_id": "A", "prop1": "foo"... }
        if not cache.get(photo[key_field], None):
            cache[photo[key_field]] = {key_field: photo[key_field]}

        # Pass in a value, not a reference
        cache_entry = copy.deepcopy(cache[photo[key_field]])

        item_update = get_cache_update_for_item(
            cache_entry,
            flickr_ctx['cur_time'],
            generator.settings.get('FLICKR_INSERT_CACHE_CFG')
        )

        # Update cache item as needed
        if item_update['status'] == 'needs_update':
            updated_item = get_info_from_flickr(
                flickr_ctx['flickr_conn'], photo[key_field])

            if updated_item:
                item_update.update(updated_item)
                next_update_time = get_next_update_time(
                    flickr_ctx['cur_time'], cache_cfg)

                item_update.update({
                    'last_updated': flickr_ctx['cur_time'],
                    'last_updated_str': epoch_to_str(flickr_ctx['cur_time']),
                    'next_update': next_update_time,
                    'next_update_str': epoch_to_str(next_update_time)
                })

                cache[photo[key_field]] = item_update
                photo.update(item_update)
            else:
                # todo: add additional error handling
                pass

        if item_update['status'] == 'ok':
            photo.update(cache_entry)

        # Update the image url (needed to show the same picture with
        # different sizes on the same page)
        photo.update(ensure_photo_insert_image_url(photo))

        # Copy and update the context for this picture and (re)render
        context = generator.context.copy()
        context.update(photo)
        replacement = flickr_ctx['template'].render(context)
        document._content = document._content.replace(match[0], replacement)


def get_cache_update_for_item(cache_entry, cur_time, cache_cfg):
    # Caching works on three levels
    # 1.  If item was updated very recently, it probably was in the same
    # session, so return early without updates.  Default is one hour
    # 2.  If item was updated somewhat recently, it should be checked for any
    #  updates.  Default for this is three days.
    # 3.  Items should be checked from time to time for new updates.  Default
    #  is 14 days.

    # Returns an updated cache item
    cache_update = {}
    cache_update['status'] = "ok"  # status is ok, no_change, or needs_update

    # Return early if item is requested within X increments of last update
    item_last_updated = make_int(cache_entry.get('last_updated', 0))
    if cur_time - item_last_updated < cache_cfg['session_interval']:
        return cache_update

    key_name = cache_cfg['key_field']
    cache_id = cache_entry[key_name]
    next_update_time = cur_time + cache_cfg['refresh_interval']

    # If this pic was last updated recently, or has no last update
    if item_last_updated > int(cur_time - cache_cfg['recent_interval']) \
            or item_last_updated == 0:
        cache_update['status'] = 'needs_update'
        # Add randomness to smear out updates, for when large numbers of
        # items are recently added to cache
        next_update_time = get_next_update_time(cur_time, cache_cfg)

    # if an update is due, check for updates
    if make_int(cache_entry.get('next_update', cur_time + 1)) <= cur_time:
        cache_update['status'] = 'needs_update'

    if cache_update['status'] == 'needs_update':
        cache_update.update({key_name: cache_id})
        cache_update['next_update'] = next_update_time
        cache_update['next_update_str'] = epoch_to_str(next_update_time)

    return cache_update


def get_next_update_time(cur_time, cache_cfg):
    return cur_time + random.randint(
        cache_cfg['recent_interval'] + cache_cfg['increment'],
        cache_cfg['refresh_interval'])


def get_info_from_flickr(flickr, photo_id):
    _flickr_info = {}
    # Add additional information from Flickr
    logger.info('[flickr_insert]:'
                ' Fetching info from Flickr for ' + photo_id)

    try:
        flickr_response = flickr.photos.getInfo(photo_id=photo_id,
                                                format='parsed-json')
    except flickrapi.exceptions.FlickrError as e:
        _flickr_info.update({"flickr_error": str(e)})
        return _flickr_info

    if flickr_response['stat'] != 'ok':
        return _flickr_info

    # All photo metadata is in the 'photo' key
    response = flickr_response['photo']

    # Build the base url for the photo's direct link for caching.  For example:
    #
    #   https://farm{farm-id}.staticflickr.com/
    #   {server-id}/{id}_{secret}_[mstzb].jpg will become
    #
    #   https://farm9.staticflickr.com/8579/16736042621_7cfe88c078_z.jpg
    #
    # Note that the image size suffix and extension of z.jpg are not part of
    #  the base URL, but are added on a per-photo-use basis

    u = []
    u.append("https://farm" + str(response['farm']))
    u.append(".staticflickr.com/" + str(response['server'] + "/"))
    u.append(str(response['id']) + "_")
    u.append(str(response['secret']) + "_")

    _flickr_info['insert_image_url_base'] = "".join(u)

    # Update title (the actual caption visible on page)
    _flickr_info['title'] = response['title'].get('_content', "")

    return _flickr_info


def load_cache_from_csv(filename, key_name="id"):
    _cache = {}

    try:
        with open(filename) as csvfile:
            reader = csv.DictReader(csvfile)
            _cache = {row[key_name]: row for row in reader}
    except FileNotFoundError:
        save_cache_to_csv(_cache, filename=filename)

    return _cache


def save_cache_to_csv(cache, filename="cache.csv", fieldnames=None,
                      key_name="id"):
    if not fieldnames:
        fieldnames = []
    with open(filename, 'w') as csv_file:
        csv_fieldnames = [key_name, ]
        csv_fieldnames.extend(fieldnames)

        writer = csv.DictWriter(csv_file, fieldnames=csv_fieldnames,
                                extrasaction='ignore')
        writer.writeheader()
        for cache_key, entry in sorted(cache.items()):
            writer.writerow(entry)


def make_int(s):
    if isinstance(s, int):
        return s
    s = s.strip()  # return 0 for empty string
    return int(s) if s else 0


def epoch_to_str(epoch):
    return time.strftime("%Y-%m%d, %H:%M:%S", time.localtime(epoch))


def register():
    signals.generator_init.connect(init_flickr_insert)
    signals.article_generator_finalized.connect(replace_document_tags)
    signals.page_generator_finalized.connect(replace_document_tags)
