#!/usr/bin/env python3
# Test script for the updated team detection system

import sys
import os
import json
from createArticles.detectTeam import detectTeam

def test_team_detection():
    """Test the enhanced team detection functionality with different article scenarios"""
    
    detector = detectTeam()
    
    # Test cases representing different scenarios
    test_cases = [
        {
            "name": "Single team article",
            "content": """The Kansas City Chiefs have shown remarkable consistency this season. 
            Patrick Mahomes continues to elevate his game week after week, showing why he's 
            considered one of the NFL's elite quarterbacks. Coach Andy Reid praised the team's 
            defensive effort in their recent victory. The Chiefs' upcoming schedule features 
            several tough opponents, but analysts expect them to maintain their position at the 
            top of the AFC."""
        },
        {
            "name": "Multiple teams article",
            "content": """The AFC playoff race is heating up with several teams in contention. 
            The Chiefs have maintained their dominance, while the Bills are showing signs of 
            improvement after a rocky start. Meanwhile, the Ravens continue to rely on their 
            strong defense. The Bengals have surprised many with their offensive performance, 
            and the Dolphins remain in the hunt despite injury concerns."""
        },
        {
            "name": "General NFL news",
            "content": """The NFL announced several changes to the upcoming draft process, 
            focusing on improving the experience for both teams and prospects. Commissioner 
            Roger Goodell emphasized the league's commitment to player safety with new rule 
            implementations for the upcoming season. Television ratings continue to rise across 
            all markets, showing the enduring popularity of professional football in America."""
        },
        {
            "name": "Mixed focus article",
            "content": """The Patriots have made significant changes to their coaching staff, 
            bringing in former coordinators from the Ravens and Eagles. This comes after a 
            disappointing season where they failed to make the playoffs. Around the league, 
            several teams including the Bills, Dolphins, and Jets are making strategic moves 
            to challenge the Patriots' long-standing dominance in the AFC East division."""
        }
    ]
    
    print("\n=== TEAM DETECTION TEST RESULTS ===\n")
    
    for idx, test_case in enumerate(test_cases, 1):
        print(f"Test {idx}: {test_case['name']}")
        print("-" * 40)
        print(f"Content snippet: {test_case['content'][:100]}...")
        
        # Run detection
        result = detector.detect_team(test_case['content'])
        
        # Print results
        print(f"Detected team: {result['team']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print()
    
    print("=== CUSTOM TEST ===")
    print("Enter your own article text to test the team detection:")
    print("(Enter a blank line to finish)")
    
    custom_lines = []
    while True:
        line = input()
        if not line:
            break
        custom_lines.append(line)
    
    if custom_lines:
        custom_content = "\n".join(custom_lines)
        custom_result = detector.detect_team(custom_content)
        print("\nResults for custom article:")
        print(f"Detected team: {custom_result['team']}")
        print(f"Confidence: {custom_result['confidence']:.2f}")

if __name__ == "__main__":
    test_team_detection()