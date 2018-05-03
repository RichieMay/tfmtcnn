# MIT License
# 
# Copyright (c) 2018
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import numpy as np
import cv2
import numpy.random as npr

from datasets.SimpleFaceDataset import SimpleFaceDataset
from datasets.InferenceBatch import InferenceBatch

from nets.FaceDetector import FaceDetector
from nets.NetworkFactory import NetworkFactory

from utils.convert_to_square import convert_to_square
from utils.IoU import IoU

class HardFaceDataset(SimpleFaceDataset):

	def __init__(self, name='HardFaceDataset'):
		SimpleFaceDataset.__init__(self, name)	

	def _generate_hard_samples(self, network_name, detected_boxes, minimum_face, target_root_dir):

		image_file_names = self._data['images']
		ground_truth_boxes = self._data['bboxes']
    		number_of_images = len(image_file_names)

		if(not (len(detected_boxes) == number_of_images)):
			return(False)

		image_size = NetworkFactory.network_size(network_name)

		positive_dir = os.path.join(target_root_dir, 'positive')
		part_dir = os.path.join(target_root_dir, 'part')
		negative_dir = os.path.join(target_root_dir, 'negative')

		if(not os.path.exists(positive_dir)):
    			os.makedirs(positive_dir)
		if(not os.path.exists(part_dir)):
    			os.makedirs(part_dir)
		if(not os.path.exists(negative_dir)):
    			os.makedirs(negative_dir)

		positive_file = open(SimpleFaceDataset.positive_file_name(target_root_dir), 'w')
		part_file = open(SimpleFaceDataset.part_file_name(target_root_dir), 'w')
		negative_file = open(SimpleFaceDataset.negative_file_name(target_root_dir), 'w')

    		negative_images = 0
    		positive_images = 0
    		part_images = 0

    		for image_file_path, detected_box, ground_truth_box in zip(image_file_names, detected_boxes, ground_truth_boxes):
        		ground_truth_box = np.array(ground_truth_box, dtype=np.float32).reshape(-1, 4)

        		if( detected_box.shape[0] == 0 ):
            			continue

        		detected_box = convert_to_square(detected_box)
        		detected_box[:, 0:4] = np.round(detected_box[:, 0:4])

        		current_image = cv2.imread(image_file_path)

        		neg_num = 0
        		for box in detected_box:
            			x_left, y_top, x_right, y_bottom, _ = box.astype(int)
            			width = x_right - x_left + 1
            			height = y_bottom - y_top + 1

            			if( (width < minimum_face) or (x_left < 0) or (y_top < 0) or (x_right > current_image.shape[1] - 1) or (y_bottom > current_image.shape[0] - 1) ):
                			continue

            			current_IoU = IoU(box, ground_truth_box)
            			cropped_image = current_image[y_top:y_bottom + 1, x_left:x_right + 1, :]
            			resized_image = cv2.resize(cropped_image, (image_size, image_size), interpolation=cv2.INTER_LINEAR)

            			if( (np.max(current_IoU) < SimpleFaceDataset.negative_IoU()) and (neg_num < 60) ):
                			file_path = os.path.join(negative_dir, "%s.jpg" % negative_images)
                			negative_file.write(file_path + ' 0\n')
                			cv2.imwrite(file_path, resized_image)
                			negative_images += 1
                			neg_num += 1
            			else:
                			idx = np.argmax(current_IoU)
                			assigned_gt = ground_truth_box[idx]
                			x1, y1, x2, y2 = assigned_gt

                			offset_x1 = (x1 - x_left) / float(width)
                			offset_y1 = (y1 - y_top) / float(height)
                			offset_x2 = (x2 - x_right) / float(width)
                			offset_y2 = (y2 - y_bottom) / float(height)

                			if( np.max(current_IoU) >= SimpleFaceDataset.positive_IoU() ):
                    				file_path = os.path.join(positive_dir, "%s.jpg" % positive_images)
                    				positive_file.write(file_path + ' 1 %.2f %.2f %.2f %.2f\n' % (offset_x1, offset_y1, offset_x2, offset_y2))
                    				cv2.imwrite(file_path, resized_image)
                    				positive_images += 1

                			elif( np.max(current_IoU) >= SimpleFaceDataset.part_IoU() ):
                    				file_path = os.path.join(part_dir, "%s.jpg" % part_images)
                    				part_file.write(file_path + ' -1 %.2f %.2f %.2f %.2f\n' % (offset_x1, offset_y1, offset_x2, offset_y2))
                    				cv2.imwrite(file_path, resized_image)
                    				part_images += 1
    		negative_file.close()
    		part_file.close()
    		positive_file.close()

		return(True)

	def generate_samples(self, annotation_image_dir, annotation_file_name, model_train_dir, network_name, minimum_face, target_root_dir):

		if(not self._read(annotation_image_dir, annotation_file_name)):
			return(False)

		test_data = InferenceBatch(self._data['images'])

		if(not model_train_dir):
			model_train_dir = NetworkFactory.model_train_dir()			
		face_detector = FaceDetector(model_train_dir)

		previous_network = NetworkFactory.previous_network(network_name)
		detected_boxes, landmarks = face_detector.detect_face(test_data, previous_network)

		return(self._generate_hard_samples(network_name, detected_boxes, minimum_face, target_root_dir))

