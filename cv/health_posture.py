# health_posture.py

import cv2
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)

DEBUG_MODE = False  # Set to True to enable debugging visuals


def calculate_health_percentage(health_bar_image):
    """
    Calculate the health percentage based on the health bar length.

    Args:
        health_bar_image (np.ndarray): Image of the health bar.

    Returns:
        float: Health percentage (0 to 100).
    """
    hsv = cv2.cvtColor(health_bar_image, cv2.COLOR_BGR2HSV)

    # Define red color range in HSV
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 100, 100])
    upper_red2 = np.array([180, 255, 255])

    # Create masks for red color
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)

    # Apply morphological operations to clean the mask
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)

    # Apply adaptive threshold
    _, binary_mask = cv2.threshold(mask, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Find contours in the mask
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        # Assume the largest contour is the health bar
        largest_contour = max(contours, key=cv2.contourArea)
        _, _, w, _ = cv2.boundingRect(largest_contour)
        health_percentage = (w / binary_mask.shape[1]) * 100
        health_percentage = np.clip(health_percentage, 0, 100)
    else:
        health_percentage = 0

    if DEBUG_MODE:
        cv2.imshow('Health Mask', mask)

    return health_percentage


def calculate_posture_percentage(posture_bar_image):
    """
    Calculate the posture percentage based on the posture bar length.

    Args:
        posture_bar_image (np.ndarray): Image of the posture bar.

    Returns:
        float: Posture percentage (0 to 100).
    """
    hsv = cv2.cvtColor(posture_bar_image, cv2.COLOR_BGR2HSV)

    # Define posture bar color range (yellow/orange)
    lower_color = np.array([15, 100, 100])
    upper_color = np.array([35, 255, 255])

    mask = cv2.inRange(hsv, lower_color, upper_color)
    mask = cv2.GaussianBlur(mask, (3, 3), 0)

    # Project the mask along the vertical axis to get a horizontal profile
    profile = np.sum(mask, axis=0)

    # Dynamic threshold based on 30% of the maximum profile value
    threshold = np.max(profile) * 0.3
    indices = np.where(profile > threshold)[0]

    if len(indices) > 0:
        posture_bar_length = indices[-1] - indices[0]
        posture_percentage = (posture_bar_length / mask.shape[1]) * 100
        posture_percentage = np.clip(posture_percentage, 0, 100)
    else:
        posture_percentage = 0

    if DEBUG_MODE:
        cv2.imshow('Posture Mask', mask)

    return posture_percentage


def extract_health(player_health_img, boss_health_img):
    """
    Extract health percentages for the player and the boss.

    Args:
        player_health_img (np.ndarray): Image containing the player's health bar.
        boss_health_img (np.ndarray): Image containing the boss's health bar.

    Returns:
        tuple: (player_health, boss_health)
    """
    player_health = calculate_health_percentage(player_health_img)
    boss_health = calculate_health_percentage(boss_health_img)

    logging.info(f'Player Health: {player_health:.2f}%, Boss Health: {boss_health:.2f}%')

    if DEBUG_MODE:
        cv2.imshow('Player Health Bar', player_health_img)
        cv2.imshow('Boss Health Bar', boss_health_img)

    return player_health, boss_health


def extract_posture(player_posture_img, boss_posture_img):
    """
    Extract posture percentages for the player and the boss.

    Args:
        player_posture_img (np.ndarray): Image containing the player's posture bar.
        boss_posture_img (np.ndarray): Image containing the boss's posture bar.

    Returns:
        tuple: (player_posture, boss_posture)
    """
    player_posture = calculate_posture_percentage(player_posture_img)
    boss_posture = calculate_posture_percentage(boss_posture_img)

    logging.info(f'Player Posture: {player_posture:.2f}%, Boss Posture: {boss_posture:.2f}%')

    if DEBUG_MODE:
        cv2.imshow('Player Posture Bar', player_posture_img)
        cv2.imshow('Boss Posture Bar', boss_posture_img)

    return player_posture, boss_posture