flickr_insert
==================

The flickr_insert plugin for Pelican lets you the ability to insert Flickr images into static document content.

- Various image sizes are supported
- Captions on the image can be turned on or off
- Images can be rendered inline, or floated to the right

## Usage

To insert an image into a Pelican document, a simple tag looks as this:

[flickr:url=https://flic.kr/p/BWmPQ5]

The 'short' URL for a particular Flickr image can be found by opening the image in the Flickr app on iOS or Android,
clicking the forward button, and choosing 'Copy URL'.  It can also be found when viewing the image in a web browser.

### More advanced usage

Tags support additionalparameters, such as this tag:

[flickr:url=https://flic.kr/p/BWmPQ5,size=small240,caption=true,float=right]

Currently 'size', 'caption', and 'float' are supported.

### A note on caching

Some information--namely the photo captions--are cached after they're retrieved from Flickr.  This really speeds up the
site generation process when hundreds of pictures are included in the Pelican site.

The caching works on three levels; see code for details.

## Limitations

Currently only Markdown is tested.  RST might be supported, it just hasn't been tested.

## Some history

I wrote this so that I could add pictures to blog posts using just my iPhone.

You can see an [example page here](http://dan.marmot.net/2015/06/19/past-truckee/)

## Testing

Unit tests for Python 2.6, 2.7.10, 3.4.3, and 3.5 are provided.

Run unit tests with 'tox'