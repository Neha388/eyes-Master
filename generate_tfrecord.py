from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import io
import pandas as pd
import tensorflow as tf
import sys

sys.path.append("../../models/research")

from PIL import Image
from object_detection.utils import dataset_util
from collections import namedtuple, OrderedDict
from absl import app, flags

FLAGS = flags.FLAGS

flags.DEFINE_string("csv_input", "", "Path to the CSV input")
flags.DEFINE_string("output_path", "", "Path to output TFRecord")
flags.DEFINE_string("label_map", "", "Path to the `label_map.pbtxt`")
flags.DEFINE_string("img_path", "", "Path to images")

def split(df, group):
    data = namedtuple("data", ["filename", "object"])
    gb = df.groupby(group)
    return [data(filename, gb.get_group(x)) for filename, x in zip(gb.groups.keys(), gb.groups)]

def create_tf_example(group, path, label_map):
    with tf.io.gfile.GFile(os.path.join(path, "{}".format(group.filename)), "rb") as fid:
        encoded_jpg = fid.read()
    encoded_jpg_io = io.BytesIO(encoded_jpg)
    image = Image.open(encoded_jpg_io)
    width, height = image.size

    filename = group.filename.encode("utf8")
    image_format = b"jpg"
    xmins = []
    xmaxs = []
    ymins = []
    ymaxs = []
    classes_text = []
    classes = []

    for index, row in group.object.iterrows():
        xmins.append(row["xmin"] / width)
        xmaxs.append(row["xmax"] / width)
        ymins.append(row["ymin"] / height)
        ymaxs.append(row["ymax"] / height)
        classes_text.append(row["class"].encode("utf8"))
        class_index = label_map.get(row["class"])
        assert class_index is not None, "class label: `{}` not found in label_map: {}".format(row["class"], label_map)
        classes.append(class_index)

    tf_example = tf.train.Example(features=tf.train.Features(feature={
        "image/height": dataset_util.int64_feature(height),
        "image/width": dataset_util.int64_feature(width),
        "image/filename": dataset_util.bytes_feature(filename),
        "image/source_id": dataset_util.bytes_feature(filename),
        "image/encoded": dataset_util.bytes_feature(encoded_jpg),
        "image/format": dataset_util.bytes_feature(image_format),
        "image/object/bbox/xmin": dataset_util.float_list_feature(xmins),
        "image/object/bbox/xmax": dataset_util.float_list_feature(xmaxs),
        "image/object/bbox/ymin": dataset_util.float_list_feature(ymins),
        "image/object/bbox/ymax": dataset_util.float_list_feature(ymaxs),
        "image/object/class/text": dataset_util.bytes_list_feature(classes_text),
        "image/object/class/label": dataset_util.int64_list_feature(classes),
    }))
    return tf_example

def main(_):
    writer = tf.io.TFRecordWriter(FLAGS.output_path)
    path = os.path.join(os.getcwd(), FLAGS.img_path)
    examples = pd.read_csv(FLAGS.csv_input)

    from object_detection.utils import label_map_util

    label_map = label_map_util.load_labelmap(FLAGS.label_map)
    categories = label_map_util.convert_label_map_to_categories(label_map, max_num_classes=90, use_display_name=True)
    category_index = label_map_util.create_category_index(categories)
    label_map = {v['name']: v['id'] for k, v in category_index.items()}

    grouped = split(examples, "filename")
    for group in grouped:
        tf_example = create_tf_example(group, path, label_map)
        writer.write(tf_example.SerializeToString())

    writer.close()
    output_path = os.path.join(os.getcwd(), FLAGS.output_path)
    print("Successfully created the TFRecords: {}".format(output_path))

if __name__ == "__main__":
    app.run(main)
