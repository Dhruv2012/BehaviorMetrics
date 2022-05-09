"""
    Robot: F1
    Framework: keras
    Number of networks: 1
    Network type: None
    Predicionts:
        linear speed(v)
        angular speed(w)

"""

import tensorflow as tf
import numpy as np
import cv2
import time
import os

from utils.constants import PRETRAINED_MODELS_DIR, ROOT_PATH
from os import path
from albumentations import (
    Compose, Normalize
)
from utils.gradcam.gradcam import GradCAM

PRETRAINED_MODELS = ROOT_PATH + '/' + PRETRAINED_MODELS_DIR + 'tf_models/'


class Brain:
    """Specific brain for the f1 robot. See header."""

    def __init__(self, sensors, actuators, model=None, handler=None, config=None):
        """Constructor of the class.

        Arguments:
            sensors {robot.sensors.Sensors} -- Sensors instance of the robot
            actuators {robot.actuators.Actuators} -- Actuators instance of the robot

        Keyword Arguments:
            handler {brains.brain_handler.Brains} -- Handler of the current brain. Communication with the controller
            (default: {None})
        """
        self.motors = actuators.get_motor('motors_0')
        self.camera = sensors.get_camera('camera_0')
        self.handler = handler
        self.cont = 0
        self.inference_times = []
        self.config = config

        if self.config['GPU'] is False:
            os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
        import tensorflow as tf

        self.gpu_inference = True if tf.test.gpu_device_name() else False

        if model:
            if not path.exists(PRETRAINED_MODELS + model):
                print("File " + model + " cannot be found in " + PRETRAINED_MODELS)

            self.net = tf.keras.models.load_model(PRETRAINED_MODELS + model)
            print(self.net.summary())
        else:
            print("** Brain not loaded **")
            print("- Models path: " + PRETRAINED_MODELS)
            print("- Model: " + str(model))

    def update_frame(self, frame_id, data):
        """Update the information to be shown in one of the GUI's frames.

        Arguments:
            frame_id {str} -- Id of the frame that will represent the data
            data {*} -- Data to be shown in the frame. Depending on the type of frame (rgbimage, laser, pose3d, etc)
        """
        self.handler.update_frame(frame_id, data)


    def execute(self):
        """Main loop of the brain. This will be called iteratively each TIME_CYCLE (see pilot.py)"""

        self.cont += 1

        image = self.camera.getImage().data
        # image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        if self.cont == 1:
            self.first_image = image

        self.update_frame('frame_0', image)

        try:
            if self.config['ImageCropped']:
                image = image[240:480, 0:640]
            if 'ImageSize' in self.config:
                img = cv2.resize(image, (self.config['ImageSize'][0], self.config['ImageSize'][1]))
            else:
                img = image
            orig = img
            if self.config['ImageNormalized']:
                AUGMENTATIONS_TEST = Compose([
                    Normalize()
                ])
                image = AUGMENTATIONS_TEST(image=img)
                img = image["image"]

            img = np.expand_dims(img, axis=0)
            start_time = time.time()
            prediction = self.net.predict(img)
            self.inference_times.append(time.time() - start_time)

            if self.config['PredictionsNormalized']:
                prediction_v = prediction[0][0] * (24 - (6.5)) + (6.5)
                prediction_w = prediction[0][1] * (7.1 - (-7.1)) + (-7.1)
            else:
                prediction_v = prediction[0][0]
                prediction_w = prediction[0][1]

            if prediction_w != '' and prediction_w != '':
                self.motors.sendV(prediction_v)
                self.motors.sendW(prediction_w)

            # GradCAM from image
            i = np.argmax(prediction[0])
            cam = GradCAM(self.net, i)
            heatmap = cam.compute_heatmap(img)
            heatmap = cv2.resize(heatmap, (heatmap.shape[1], heatmap.shape[0]))
            (heatmap, output) = cam.overlay_heatmap(heatmap, orig, alpha=0.5)
            self.update_frame('frame_1', output)

        except Exception as err:
            print(err)