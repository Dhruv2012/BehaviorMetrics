'''

Clase metrics con todo lo necesario para sacar las métricas para uno o varios ficheros. 
 * Debe funcionar de forma acoplada a la aplicación principal (Controller).
 * Debe funcionar de forma desacoplada de la app principal llamándola por comando.


'''

from bagpy import bagreader
import pandas as pd
import numpy as np
from datetime import datetime
import shutil


class Metrics:
    
    def __init__(self):
        pass
    
    
    def is_finish_line(self, point, start_point):
        current_point = np.array([point['pose.pose.position.x'], point['pose.pose.position.y']])
        start_point = np.array([start_point['pose.pose.position.x'], start_point['pose.pose.position.y']])

        dist = (start_point - current_point) ** 2
        dist = np.sum(dist, axis=0)
        dist = np.sqrt(dist)
        if dist < 0.5:
            return True
        return False

    def circuit_distance_completed(self, checkpoints, lap_point):
        previous_point = []
        diameter = 0
        for i, point in enumerate(checkpoints):
            current_point = np.array([point['pose.pose.position.x'], point['pose.pose.position.y']])
            if i is not 0:
                dist = (previous_point - current_point) ** 2
                dist = np.sum(dist, axis=0)
                dist = np.sqrt(dist)
                diameter += dist
            if point is lap_point:
                break
            previous_point = np.array([point['pose.pose.position.x'], point['pose.pose.position.y']])
        return diameter

    def read_perfect_lap_rosbag(self, ground_truth_lap_file):
        bag_reader = bagreader(ground_truth_lap_file)
        csvfiles = []
        for topic in bag_reader.topics:
            data = bag_reader.message_by_topic(topic)
            csvfiles.append(data)

        data_file = 'full-lap/F1ROS-odom.csv'
        dataframe_pose = pd.read_csv(data_file)
        checkpoints = []
        for index, row in dataframe_pose.iterrows():
            checkpoints.append(row)

        perfect_lap_checkpoints = checkpoints
        start_point = checkpoints[0]
        for x, point in enumerate(checkpoints):
            if x is not 0 and point['header.stamp.secs'] - 10 > start_point['header.stamp.secs'] and self.is_finish_line(point, start_point) :
                lap_point = point

        circuit_diameter = self.circuit_distance_completed(checkpoints, lap_point)
        shutil.rmtree(ground_truth_lap_file.split('.bag')[0])
        return perfect_lap_checkpoints, circuit_diameter


    def lap_percentage_completed(self, stats_filename, perfect_lap_checkpoints, circuit_diameter):
        lap_statistics = {}
        bag_reader = bagreader(stats_filename)
        csvfiles = []
        for topic in bag_reader.topics:
            data = bag_reader.message_by_topic(topic)
            csvfiles.append(data)

        data_file = stats_filename.split('.bag')[0] + '/F1ROS-odom.csv'
        dataframe_pose = pd.read_csv(data_file)
        checkpoints = []
        for index, row in dataframe_pose.iterrows():
            checkpoints.append(row)

        start_point = checkpoints[0]
        end_point = checkpoints[len(checkpoints)-1]
        lap_statistics['completed_distance'] = self.circuit_distance_completed(checkpoints, end_point)
        lap_statistics['percentage_completed'] = (lap_statistics['completed_distance'] / circuit_diameter) * 100      
        lap_statistics = self.get_robot_orientation_score(perfect_lap_checkpoints, checkpoints, lap_statistics)
        if lap_statistics['percentage_completed'] > 100:
            start_point = checkpoints[0]
            for x, point in enumerate(checkpoints):
                if x is not 0 and point['header.stamp.secs'] - 10 > start_point['header.stamp.secs'] and self.is_finish_line(point, start_point) :
                    lap_point = point

            seconds_start = start_point['header.stamp.secs']
            seconds_end = lap_point['header.stamp.secs']
            lap_statistics['lap_seconds'] = seconds_end - seconds_start
            lap_statistics['circuit_diameter'] = self.circuit_distance_completed(checkpoints, lap_point)
            lap_statistics['average_speed'] = self.circuit_distance_completed(checkpoints, lap_point)/lap_statistics['lap_seconds']

        shutil.rmtree(stats_filename.split('.bag')[0])
        return lap_statistics

    def get_robot_orientation_score(self, perfect_lap_checkpoints, checkpoints, lap_statistics):
        start_time = datetime.now()
        min_dists = []
        previous_checkpoint_x = 0
        for checkpoint in checkpoints:
            min_dist = 100
            ten_checkpoints = 10
            for x, perfect_checkpoint in enumerate(perfect_lap_checkpoints):
                if x >= previous_checkpoint_x:
                    if abs(checkpoint['pose.pose.position.x'] - perfect_checkpoint['pose.pose.position.x']) < 1.5 and abs(checkpoint['pose.pose.position.y'] - perfect_checkpoint['pose.pose.position.y']) < 1.5:
                        if (ten_checkpoints > 0):
                            if ten_checkpoints == 10:
                                previous_checkpoint_x = x - 10
                            ten_checkpoints -= 1
                            point_1 = np.array([checkpoint['pose.pose.position.x'], checkpoint['pose.pose.position.y']])
                            point_2 = np.array([perfect_checkpoint['pose.pose.position.x'], perfect_checkpoint['pose.pose.position.y']])
                            dist = (point_2 - point_1) ** 2
                            dist = np.sum(dist, axis=0)
                            dist = np.sqrt(dist)
                            if dist < min_dist:
                                min_dist = dist 
                        else:
                            break
            min_dists.append(min_dist)

        end_time = datetime.now()
        lap_statistics['orientation_mae'] = sum(min_dists) / len(min_dists)
        lap_statistics['orientation_total_err'] = sum(min_dists)
        return lap_statistics