import os
import csv
import collections
import itertools
import numpy as np
import multiprocessing as mp
import matplotlib.pyplot as plt


# Functions for getting features from files/directories

def feature_from_file(file_path, feature_type="head", byte_num=512):  # will add more feature_type later
    """Retrieves features from a file.

    Parameters:
    feature_type (str): "head" to get bytes from head of the file.
    byte_num (int): Number of bytes to grab.
    file_path (str): File path of file to get features from.

    Returns:
    List of bytes from file_path.
    """
    if feature_type == "head":
        with open(file_path, 'rb') as f:
            byte = f.read(1)
            index = 1
            features = []

            while byte and index <= byte_num:
                features.append(byte)
                index += 1
                byte = f.read(1)

            if len(features) < byte_num:
                features.extend([b'' for _ in range(byte_num - len(features))])

            assert len(features) == byte_num
            return features
    else:
        print("Invalid feature type")


def feature_from_dir(dir_path, feature_type="head", byte_num=512):# :( can't figure out how to implement multiprocessing with multiple parameters
    """Takes a directory and grabs features from each file.

    Parameters:
    dir_path (str): Path of directory to take features from.
    feature_type (str): Type of features to get.
    byte_num (str): Number of features to take

    Return:
    features (list): 2D list of byte_num bytes from each fie in dir_path.
    """
    file_paths = []
    features = []

    for (dirpath, dirnames, filenames) in os.walk(dir_path):
        for filename in filenames:
            file_paths.append(os.path.join(dirpath, filename))

    pools = mp.Pool()

    for feature in pools.imap(feature_from_file, file_paths):
        features.append(feature)

    pools.close()
    pools.join()

    return features


def translate_bytes(dir_features):
    """Translates bytes into integers.

    Parameter:
    dir_features (list): 2D list of bytes.

    Return:
    translated_features (numpy array): dir_features with bytes translated to integers.
    """
    translated_features = np.zeros((len(dir_features), len(dir_features[0])))

    for idx, file_features in enumerate(dir_features):
        x = np.array([int.from_bytes(c, byteorder="big") for c in file_features])
        translated_features[idx] = x

    return translated_features


def grab_labels(csv_path):
    """Returns the file paths and file labels from a naivetruth csv.

    Parameter:
    csv_path (str): Path of csv file to take labels and paths from.

    Returns:
    labels (list): List of label strings from csv_path.
    file_paths (list): List of file_paths from csv_path.
    """
    labels = []
    file_paths = []

    with open(csv_path) as label_file:
        csv_reader = csv.reader(label_file, delimiter=',')
        for row in csv_reader:
            file_paths.append(row[0])
            labels.append(row[2])

    labels.pop(0)
    file_paths.pop(0)

    return labels, file_paths


def flatten(lst):
    flattened = []
    for item in lst:
        if isinstance(item, list):
            flattened.extend(item)
        else:
            flattened.append(item)

    return flattened


class LabelEncoder:
    """
    Label encodes data values to numerical values.
    """
    def __init__(self):
        self.keys = {}
        self.inverse_keys = {}

    def fit(self, labels):
        """Creates a dictionary of unique keys given a list of labels.

        Parameter:
        labels (list (a)): List of any data type representing labels.
        """
        for idx, label in enumerate(labels):
            if ' ' in label:
                labels[idx] = label.split(' ')

        labels = flatten(labels)

        unique_labels = list(set([label for label in labels if not (isinstance(label, list))]))
        unique_labels.sort()

        for idx, unique_label in enumerate(unique_labels):
            self.keys.update({unique_label: idx + 1})
            self.inverse_keys.update({idx + 1: unique_label})

    def single_transform(self, label):
        assert self.keys[label], "Label not found"
        return self.keys[label]

    def transform(self, labels):
        """Turns a list of labels into a list of numerical values.

        E.g. ['a', 'b', 'a b'] -> [1, 2, [1, 2]]

        Parameter:
        labels (list (a)): List of labels to transform into numerical values.

        Return:
        labels (list (int)): List of numerical values.
        """
        for idx, label in enumerate(labels):
            if ' ' in label:
                labels[idx] = label.split(' ')

        for idx, label in enumerate(labels):
            if isinstance(label, list):
                labels[idx] = [self.single_transform(x) for x in label]
            else:
                labels[idx] = self.single_transform(label)

        return labels

    def fit_transform(self, labels):
        self.fit(labels)
        return self.transform(labels)

    def single_inverse_transform(self, encoded_label):
        assert self.inverse_keys[encoded_label], "Label not found"
        return self.inverse_keys[encoded_label]

    def inverse_transform(self, encoded_labels):
        """Turns encoded labels into their original values.

        Parameter:
        encoded_labels (list (int)): Labels encoded using the .fit() method.

        Return:
        encoded_labels (list (a)): Original values of encoded_label input.
        """
        for idx, encoded_label in enumerate(encoded_labels):
            if isinstance(encoded_label, list):
                encoded_labels[idx] = [self.single_inverse_transform(x) for x in encoded_label]
            else:
                encoded_labels[idx] = self.single_inverse_transform(encoded_label)

        return encoded_labels


def multilabel_to_categorical(encoded_labels):
    """Hot-encodes labels as returned by multilabel_label_encoder.

    E.g. [1, 2, [1, 2]] -> [[1, 0], [0, 1], [1, 1]]

    Parameter:
    encoded_labels (list (int)): Labels as returned by multilabel_label_encoder.

    Return:
    empty_categorical (list (list (int)): Returns hot-encoded version of encoded_labels.
    """
    categorical_length = max(flatten(encoded_labels))
    empty_categorical = [[0 for _ in range(categorical_length)] for _ in range(len(encoded_labels))]

    for idx, encoded_label in enumerate(encoded_labels):
        if not(isinstance(encoded_label, list)):
            empty_categorical[idx][encoded_label - 1] = 1
        else:
            for label in encoded_label:
                empty_categorical[idx][label - 1] = 1

    return empty_categorical


def fix_multilabel(csv_path):
    """Takes a csv label file with multiple labels for paths and merges
    the labels together in a new csv file.

    :param csv_path:
    :return:
    """
    labels = []
    file_paths = []
    new_file_paths = []
    new_labels = []
    duplicate_paths = {}

    with open(csv_path) as label_file:
        csv_reader = csv.reader(label_file, delimiter=',')
        for row in csv_reader:
            file_paths.append(row[0])
            labels.append(row[2])

    labels.pop(0)
    file_paths.pop(0)

    unique_paths, counts = np.unique(file_paths, return_counts=True)

    paths_to_remove = []

    for idx, unique_path in enumerate(unique_paths):
        if counts[idx] > 1:
            duplicate_paths.update({unique_path: counts[idx]})
        else:
            paths_to_remove.append(unique_path)

    print("Cleaning paths...")

    for idx, path in enumerate(paths_to_remove):
        if idx % 1000 == 0:
            print("{}/".format(idx, (len(paths_to_remove))))
        for path_idx in range(len(file_paths)):
            if path == file_paths[path_idx]:
                new_file_paths.append(file_paths[path_idx])
                new_labels.append(labels[path_idx])
                del file_paths[path_idx]
                del labels[path_idx]
                break

    print("Done cleaning")
    print("Fixing labels...")

    for duplicate_path in duplicate_paths:
        multilabel = []

        for idx, path in enumerate(file_paths):
            if len(multilabel) == duplicate_paths[duplicate_path]:
                break
            elif path == duplicate_path:
                multilabel.append(labels[idx])

        new_file_paths.append(duplicate_path)
        new_labels.append(' '.join(multilabel))

    assert len(new_file_paths) == len(new_labels), "Missing file paths or labels"

    new_rows = zip(new_file_paths, [0 for _ in range(len(new_file_paths) + 1)], new_labels)

    print("Done fixing labels")

    with open(os.path.join(os.path.dirname(csv_path),
                           'new' + os.path.basename(csv_path)), 'w') as new_label_file:
        label_file_writer = csv.writer(new_label_file, delimiter=',')
        for new_row in new_rows:
            label_file_writer.writerow(new_row)

    print('Done rewriting csv')


def feature_from_list(file_paths):
    """Grabs features from a list of file paths.

    Parameter:
    file_paths (str): List of file paths to get features from.

    Return:
    features (list): List of features from files.
    """
    features = []

    pools = mp.Pool()

    for feature in pools.imap(feature_from_file, file_paths):
        features.append(feature)

    pools.close()
    pools.join()

    return features


# Functions to create a confusion matrix


def convert_to_index(array_categorical):
    """Turns a list of numpy array ouputted from a categorical classifier into a
    single integer.

    Parameter:
    array_categorical (list): List of numpy arrays ouputted from a categorical classifier.

    Return:
    array_index (list): List of integers.
    """
    array_index = [np.argmax(array_temp) for array_temp in array_categorical]
    return array_index


def multiclass_convert_to_index(array_categorical):
    array_index = list(map((lambda x: [1 if i > 0.5 else 0 for i in x]), array_categorical))

    for idx, index in enumerate(array_index):
        labels = list(map((lambda x: x + 1), np.argwhere(index == np.amax(index)).flatten().tolist()))
        if len(labels) == 1:
            array_index[idx] = labels[0]
        else:
            array_index[idx] = labels

    return array_index


def plot_confusion_matrix(cm,
                          normalize=False,
                          title='Confusion matrix',
                          cmap=plt.cm.Blues):
    """
    This function modified to plots the ConfusionMatrix object.
    Normalization can be applied by setting `normalize=True`.

    Code Reference :
    http://scikit-learn.org/stable/auto_examples/model_selection/plot_confusion_matrix.html

    This script is derived from PyCM repository: https://github.com/sepandhaghighi/pycm

    """

    plt_cm = []
    for i in cm.classes:
        row = []
        for j in cm.classes:
            row.append(cm.table[i][j])
        plt_cm.append(row)
    plt_cm = np.array(plt_cm)
    if normalize:
        plt_cm = plt_cm.astype('float') / plt_cm.sum(axis=1)[:, np.newaxis]
    plt.imshow(plt_cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(cm.classes))
    plt.xticks(tick_marks, cm.classes, rotation=45)
    plt.yticks(tick_marks, cm.classes)

    fmt = '.2f' if normalize else 'd'
    thresh = plt_cm.max() / 2.
    for i, j in itertools.product(range(plt_cm.shape[0]), range(plt_cm.shape[1])):
        plt.text(j, i, format(plt_cm[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if plt_cm[i, j] > thresh else "black")

    plt.tight_layout()
    plt.ylabel('Actual')
    plt.xlabel('Predict')

