#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug script to find problematic JS tokens in REQUESTS_TEMPLATE
"""

import re
import sys

def analyze_js_tokens(template_content):
    """Analyze template content for potential JS parsing issues"""
    issues = []
    
    # Extract script blocks
    script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', template_content, re.DOTALL | re.IGNORECASE)
    
    for i, script in enumerate(script_blocks):
        print(f"\n=== SCRIPT BLOCK {i+1} ===")
        
        # Check for common issues
        lines = script.split('\n')
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('//'):
                continue
                
            # Check for unescaped newlines in strings
            if "'" in line and '\n' in line:
                issues.append(f"Script {i+1}, Line {line_num}: Potential unescaped newline in string")
                print(f"  ISSUE Line {line_num}: {line[:100]}...")
            
            # Check for template literals with newlines
            if '`' in line:
                issues.append(f"Script {i+1}, Line {line_num}: Template literal found")
                print(f"  ISSUE Line {line_num}: {line[:100]}...")
            
            # Check for Korean characters in JS strings
            if re.search(r'[가-힣]', line):
                # Check if it's properly quoted
                korean_matches = re.findall(r"'[^']*[가-힣][^']*'|\"[^\"]*[가-힣][^\"]*\"", line)
                if not korean_matches and re.search(r'[가-힣]', line):
                    issues.append(f"Script {i+1}, Line {line_num}: Unquoted Korean text")
                    print(f"  ISSUE Line {line_num}: {line[:100]}...")
            
            # Check for trailing commas in objects
            if re.search(r',\s*[}\]]', line):
                issues.append(f"Script {i+1}, Line {line_num}: Trailing comma")
                print(f"  ISSUE Line {line_num}: {line[:100]}...")
            
            # Check for unclosed strings
            single_quotes = line.count("'") - line.count("\\'")
            double_quotes = line.count('"') - line.count('\\"')
            if single_quotes % 2 != 0 or double_quotes % 2 != 0:
                issues.append(f"Script {i+1}, Line {line_num}: Unclosed string")
                print(f"  ISSUE Line {line_num}: {line[:100]}...")
    
    return issues

def main():
    try:
        with open('app_new.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract REQUESTS_TEMPLATE
        template_match = re.search(r"REQUESTS_TEMPLATE = '''(.*?)'''", content, re.DOTALL)
        if not template_match:
            print("REQUESTS_TEMPLATE not found!")
            return
        
        template_content = template_match.group(1)
        print(f"Template length: {len(template_content)} characters")
        
        issues = analyze_js_tokens(template_content)
        
        print(f"\n=== SUMMARY ===")
        print(f"Total issues found: {len(issues)}")
        for issue in issues:
            print(f"  - {issue}")
        
        if not issues:
            print("No obvious JS parsing issues found in template.")
            print("The issue might be in the rendering process or browser-specific.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
