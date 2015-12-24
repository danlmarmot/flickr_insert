import unittest
import os
import yaml
import flickr_insert

CUR_DIR = os.path.dirname(__file__)
TEST_DATA_DIR = os.path.join(CUR_DIR, 'test_data')


class TestFlickrInsert(unittest.TestCase):
    def test_get_flickr_tags(self):
        # Test content is multiple
        with open(os.path.join(
                TEST_DATA_DIR, 'get_flickr_tags.yaml'), 'r') as f:
            test_case_data = yaml.load(f)

        for single_test, expected in test_case_data.items():
            tags = flickr_insert.get_flickr_tags(single_test)

            for tag in tags:
                # verify all parameters are correctly returned
                for parameter_key, _ in tag.items():
                    self.assertEqual(tag[parameter_key],
                                     expected.get(parameter_key, None))

                # verify all expected parameters are returned
                for expected_key, _ in expected.items():
                    self.assertEqual(expected[expected_key],
                                     tag.get(expected_key, None))

    def test_get_photo_id_and_url(self):
        with open(os.path.join(
                TEST_DATA_DIR, 'get_photo_id_and_url.yaml'), 'r') as f:
            test_case_data = yaml.load(f)

        for single_test in test_case_data:
            output = flickr_insert.get_photo_id_and_url(single_test["input"])

            expected = single_test['expected']
            self.assertEqual(output['url'], expected.get('url', None))
            self.assertEqual(output['id'], expected.get('id', None))

    def test_ensure_photo_size(self):
        # Small size specified for photo
        photo = dict(size="small")
        # Confusingly, Flickr uses m as the suffix for small
        expected_output = dict(size="small", size_suffix="m")

        output = flickr_insert.ensure_photo_size(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())))

        # No size specified in photo
        photo = {}
        # Confusingly, Flickr uses z as the suffix for medium
        expected_output = dict(size="medium", size_suffix="z")
        output = flickr_insert.ensure_photo_size(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())))

    def test_ensure_photo_show_caption(self):

        # Test true results
        expected_output = dict(show_caption=True)

        photo = dict(show_caption="1")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + 'fails')

        photo = dict(show_caption="yes")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        photo = dict(show_caption="y")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        photo = dict(show_caption="True")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        photo = dict(show_caption="On")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        photo = dict(show_caption="On")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        # Test false results
        expected_output = dict(show_caption=False)

        photo = dict(show_caption="0")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        photo = dict(show_caption="no")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        photo = dict(show_caption="n")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        photo = dict(show_caption="false")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        photo = dict(show_caption="off")
        output = flickr_insert.ensure_photo_show_caption(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

    def test_ensure_photo_float(self):
        # Float is either left, right, or empty string

        # testing for right float
        expected_output = dict(float="right")

        photo = dict(float="right")
        output = flickr_insert.ensure_photo_float(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        # testing for left float
        expected_output = dict(float="left")

        photo = dict(float="Left")
        output = flickr_insert.ensure_photo_float(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        # testing for empty float
        expected_output = dict(float="")

        photo = dict(float="")
        output = flickr_insert.ensure_photo_float(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

        # testing for mispeled float
        expected_output = dict(float="")

        photo = dict(float="rihgt")
        output = flickr_insert.ensure_photo_float(photo)
        self.assertTrue(
            set(expected_output.items()).issubset(set(output.items())),
            msg=str(photo) + ' fails')

    def test_get_cache_update_for_item(self):

        cache_cfg = {
            'key_field': 'pic_id',
            'session_interval': 5,
            'recent_interval': 30,
            'refresh_interval': 140,
            'increment': 10
        }

        # test case
        description = "Never updated, needs update"
        cache_entry = {
            "pic_id": 100,
        }
        cur_time = 5
        expected = {"status": "needs_update"}

        # test case
        description = "In current session, ok (no update needed)"
        cache_entry = {
            "pic_id": 100,
            "last_updated": 2,
            "next_update": 15
        }
        cur_time = 5
        expected = {"status": "ok"}

        cache_update = flickr_insert.get_cache_update_for_item(
            cache_entry, cur_time, cache_cfg)

        for expected_key, _ in expected.items():
            self.assertEqual(expected[expected_key],
                             cache_update.get(expected_key, None))

        # test case
        description = "Not in current session, but within " \
                      "recent time window; needs update"
        cache_entry = {
            "pic_id": 100,
            "last_updated": 2,
            "next_update": 15
        }
        cur_time = 8
        expected = {"status": "needs_update"}

        cache_update = flickr_insert.get_cache_update_for_item(
            cache_entry, cur_time, cache_cfg)

        for expected_key, _ in expected.items():
            self.assertEqual(expected[expected_key],
                             cache_update.get(expected_key, None),
                             msg=description)

        # test case
        description = "Recent window elapsed, before refresh interval time; " \
                      "no update "
        cache_entry = {
            "pic_id": 100,
            "last_updated": 2,
            "next_update": 45
        }
        cur_time = 33
        expected = {"status": "ok"}

        cache_update = flickr_insert.get_cache_update_for_item(
            cache_entry, cur_time, cache_cfg)

        for expected_key, _ in expected.items():
            self.assertEqual(expected[expected_key],
                             cache_update.get(expected_key, None),
                             msg=description)

        # test case
        description = "Refresh interval time elapsed, needs update"
        cache_entry = {
            "pic_id": 100,
            "last_updated": 2,
            "next_update": 45
        }
        cur_time = 141
        expected = {"status": "needs_update"}

        cache_update = flickr_insert.get_cache_update_for_item(
            cache_entry, cur_time, cache_cfg)

        for expected_key, _ in expected.items():
            self.assertEqual(expected[expected_key],
                             cache_update.get(expected_key, None),
                             msg=description)

    def test_get_info_from_flickr(self):
        pass


if __name__ == "__main__":
    unittest.main()
