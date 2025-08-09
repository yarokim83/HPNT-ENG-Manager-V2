#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HPNT_ENG_Manager V2.0 - iOS 26 스타일 UI/UX 디자인 시스템
최신 iOS 26 디자인 언어를 적용한 모던하고 직관적인 인터페이스
"""

import os
import json
from datetime import datetime

class iOS26DesignSystem:
    """iOS 26 디자인 시스템"""
    
    def __init__(self):
        self.colors = {
            'primary': '#007AFF',      # iOS Blue
            'secondary': '#5856D6',    # iOS Purple
            'success': '#34C759',      # iOS Green
            'warning': '#FF9500',      # iOS Orange
            'danger': '#FF3B30',       # iOS Red
            'info': '#5AC8FA',         # iOS Light Blue
            'dark': '#1C1C1E',         # iOS Dark Gray
            'light': '#F2F2F7',        # iOS Light Gray
            'white': '#FFFFFF',
            'black': '#000000',
            'transparent': 'rgba(255,255,255,0.8)',
            'glass': 'rgba(255,255,255,0.25)',
            'glass_dark': 'rgba(0,0,0,0.25)'
        }
        
        self.gradients = {
            'primary': 'linear-gradient(135deg, #007AFF 0%, #5856D6 100%)',
            'success': 'linear-gradient(135deg, #34C759 0%, #30D158 100%)',
            'warning': 'linear-gradient(135deg, #FF9500 0%, #FF9F0A 100%)',
            'danger': 'linear-gradient(135deg, #FF3B30 0%, #FF453A 100%)',
            'glass': 'linear-gradient(135deg, rgba(255,255,255,0.25) 0%, rgba(255,255,255,0.1) 100%)',
            'dark_glass': 'linear-gradient(135deg, rgba(0,0,0,0.25) 0%, rgba(0,0,0,0.1) 100%)'
        }
        
        self.shadows = {
            'small': '0 2px 8px rgba(0,0,0,0.1)',
            'medium': '0 4px 16px rgba(0,0,0,0.15)',
            'large': '0 8px 32px rgba(0,0,0,0.2)',
            'glass': '0 8px 32px rgba(0,0,0,0.1), inset 0 1px 0 rgba(255,255,255,0.2)'
        }
        
        self.border_radius = {
            'small': '8px',
            'medium': '16px',
            'large': '24px',
            'xl': '32px',
            'full': '50%'
        }

def generate_ios26_css():
    """iOS 26 스타일 CSS 생성"""
    
    css = '''
/* === iOS 26 Design System === */
:root {
    /* iOS 26 Color Palette */
    --ios-blue: #007AFF;
    --ios-purple: #5856D6;
    --ios-green: #34C759;
    --ios-orange: #FF9500;
    --ios-red: #FF3B30;
    --ios-light-blue: #5AC8FA;
    --ios-dark: #1C1C1E;
    --ios-light: #F2F2F7;
    --ios-white: #FFFFFF;
    --ios-black: #000000;
    
    /* Glass Effects */
    --glass-light: rgba(255,255,255,0.25);
    --glass-dark: rgba(0,0,0,0.25);
    --glass-blur: blur(20px);
    
    /* Shadows */
    --shadow-small: 0 2px 8px rgba(0,0,0,0.1);
    --shadow-medium: 0 4px 16px rgba(0,0,0,0.15);
    --shadow-large: 0 8px 32px rgba(0,0,0,0.2);
    --shadow-glass: 0 8px 32px rgba(0,0,0,0.1), inset 0 1px 0 rgba(255,255,255,0.2);
    
    /* Border Radius */
    --radius-small: 8px;
    --radius-medium: 16px;
    --radius-large: 24px;
    --radius-xl: 32px;
    
    /* Typography */
    --font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif;
    --font-size-xs: 12px;
    --font-size-sm: 14px;
    --font-size-base: 16px;
    --font-size-lg: 18px;
    --font-size-xl: 20px;
    --font-size-2xl: 24px;
    --font-size-3xl: 32px;
    --font-size-4xl: 48px;
}

/* === Global Reset === */
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-tap-highlight-color: transparent;
    -webkit-touch-callout: none;
    -webkit-user-select: none;
    user-select: none;
}

body {
    font-family: var(--font-family);
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    overflow-x: hidden;
    color: var(--ios-dark);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* === iOS 26 Glass Morphism === */
.glass-container {
    background: var(--glass-light);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: var(--radius-large);
    box-shadow: var(--shadow-glass);
}

.glass-card {
    background: var(--glass-light);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: var(--radius-medium);
    box-shadow: var(--shadow-medium);
    transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.glass-card:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow-large);
    border-color: rgba(255,255,255,0.4);
}

/* === iOS 26 Buttons === */
.ios-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 12px 24px;
    border: none;
    border-radius: var(--radius-medium);
    font-family: var(--font-family);
    font-size: var(--font-size-base);
    font-weight: 600;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    position: relative;
    overflow: hidden;
    min-height: 44px; /* iOS Touch Target */
}

.ios-button::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    transition: left 0.5s;
}

.ios-button:hover::before {
    left: 100%;
}

.ios-button:active {
    transform: scale(0.96);
}

.ios-button-primary {
    background: linear-gradient(135deg, var(--ios-blue) 0%, var(--ios-purple) 100%);
    color: var(--ios-white);
    box-shadow: var(--shadow-medium);
}

.ios-button-success {
    background: linear-gradient(135deg, var(--ios-green) 0%, #30D158 100%);
    color: var(--ios-white);
    box-shadow: var(--shadow-medium);
}

.ios-button-warning {
    background: linear-gradient(135deg, var(--ios-orange) 0%, #FF9F0A 100%);
    color: var(--ios-white);
    box-shadow: var(--shadow-medium);
}

.ios-button-danger {
    background: linear-gradient(135deg, var(--ios-red) 0%, #FF453A 100%);
    color: var(--ios-white);
    box-shadow: var(--shadow-medium);
}

.ios-button-glass {
    background: var(--glass-light);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid rgba(255,255,255,0.3);
    color: var(--ios-dark);
    box-shadow: var(--shadow-glass);
}

/* === iOS 26 Form Elements === */
.ios-input {
    width: 100%;
    padding: 16px 20px;
    border: 2px solid rgba(0,0,0,0.1);
    border-radius: var(--radius-medium);
    font-family: var(--font-family);
    font-size: var(--font-size-base);
    background: var(--glass-light);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    color: var(--ios-dark);
    transition: all 0.3s ease;
    outline: none;
}

.ios-input:focus {
    border-color: var(--ios-blue);
    box-shadow: 0 0 0 3px rgba(0,122,255,0.1);
    background: rgba(255,255,255,0.3);
}

.ios-textarea {
    min-height: 120px;
    resize: vertical;
    font-family: var(--font-family);
}

/* === iOS 26 Cards === */
.ios-card {
    background: var(--glass-light);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: var(--radius-large);
    padding: 24px;
    box-shadow: var(--shadow-medium);
    transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.ios-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-large);
}

/* === iOS 26 Status Badges === */
.ios-badge {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: var(--radius-small);
    font-size: var(--font-size-sm);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.ios-badge-pending {
    background: rgba(255,149,0,0.2);
    color: var(--ios-orange);
    border: 1px solid rgba(255,149,0,0.3);
}

.ios-badge-approved {
    background: rgba(52,199,89,0.2);
    color: var(--ios-green);
    border: 1px solid rgba(52,199,89,0.3);
}

.ios-badge-rejected {
    background: rgba(255,59,48,0.2);
    color: var(--ios-red);
    border: 1px solid rgba(255,59,48,0.3);
}

.ios-badge-completed {
    background: rgba(88,86,214,0.2);
    color: var(--ios-purple);
    border: 1px solid rgba(88,86,214,0.3);
}

/* === iOS 26 Navigation === */
.ios-nav {
    background: var(--glass-light);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border-bottom: 1px solid rgba(255,255,255,0.2);
    padding: 16px 24px;
    position: sticky;
    top: 0;
    z-index: 1000;
}

.ios-nav-title {
    font-size: var(--font-size-2xl);
    font-weight: 700;
    color: var(--ios-dark);
    text-align: center;
}

/* === iOS 26 Grid System === */
.ios-grid {
    display: grid;
    gap: 20px;
}

.ios-grid-2 {
    grid-template-columns: repeat(2, 1fr);
}

.ios-grid-3 {
    grid-template-columns: repeat(3, 1fr);
}

.ios-grid-4 {
    grid-template-columns: repeat(4, 1fr);
}

/* === iOS 26 Animations === */
@keyframes ios-fade-in {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes ios-scale-in {
    from {
        opacity: 0;
        transform: scale(0.9);
    }
    to {
        opacity: 1;
        transform: scale(1);
    }
}

.ios-fade-in {
    animation: ios-fade-in 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.ios-scale-in {
    animation: ios-scale-in 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

/* === iOS 26 Responsive Design === */
@media (max-width: 768px) {
    .ios-grid-2,
    .ios-grid-3,
    .ios-grid-4 {
        grid-template-columns: 1fr;
    }
    
    .ios-card {
        padding: 20px;
    }
    
    .ios-button {
        width: 100%;
        margin-bottom: 12px;
    }
    
    .ios-nav-title {
        font-size: var(--font-size-xl);
    }
}

@media (max-width: 480px) {
    .ios-card {
        padding: 16px;
        border-radius: var(--radius-medium);
    }
    
    .ios-input {
        padding: 14px 16px;
        font-size: var(--font-size-base);
    }
}

/* === iOS 26 Dark Mode Support === */
@media (prefers-color-scheme: dark) {
    :root {
        --ios-dark: #FFFFFF;
        --ios-light: #1C1C1E;
        --glass-light: rgba(0,0,0,0.25);
        --glass-dark: rgba(255,255,255,0.25);
    }
    
    body {
        background: linear-gradient(135deg, #1C1C1E 0%, #2C2C2E 100%);
    }
    
    .ios-input {
        color: var(--ios-white);
        background: var(--glass-dark);
    }
    
    .ios-input:focus {
        background: rgba(0,0,0,0.3);
    }
}

/* === iOS 26 Accessibility === */
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* === iOS 26 Focus Indicators === */
.ios-button:focus-visible,
.ios-input:focus-visible {
    outline: 2px solid var(--ios-blue);
    outline-offset: 2px;
}

/* === iOS 26 Loading States === */
.ios-loading {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 2px solid rgba(255,255,255,0.3);
    border-radius: 50%;
    border-top-color: var(--ios-white);
    animation: ios-spin 1s ease-in-out infinite;
}

@keyframes ios-spin {
    to {
        transform: rotate(360deg);
    }
}

/* === iOS 26 Toast Notifications === */
.ios-toast {
    position: fixed;
    top: 20px;
    right: 20px;
    background: var(--glass-light);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: var(--radius-medium);
    padding: 16px 20px;
    box-shadow: var(--shadow-large);
    z-index: 10000;
    animation: ios-slide-in 0.3s ease-out;
}

@keyframes ios-slide-in {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

/* === iOS 26 Haptic Feedback Simulation === */
.ios-haptic {
    transition: transform 0.1s ease;
}

.ios-haptic:active {
    transform: scale(0.95);
}

/* === iOS 26 Dynamic Island Style === */
.ios-dynamic-island {
    background: var(--ios-black);
    border-radius: var(--radius-xl);
    padding: 8px 16px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--ios-white);
    font-size: var(--font-size-sm);
    font-weight: 600;
    box-shadow: var(--shadow-large);
    animation: ios-dynamic-island-expand 0.3s ease-out;
}

@keyframes ios-dynamic-island-expand {
    from {
        transform: scale(0.8);
        opacity: 0;
    }
    to {
        transform: scale(1);
        opacity: 1;
    }
}
'''
    
    return css

def generate_ios26_templates():
    """iOS 26 스타일 HTML 템플릿 생성"""
    
    # 메인 페이지 템플릿
    main_template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>🚀 HPNT Manager V2.0 - iOS 26</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="HPNT Manager">
    <meta name="theme-color" content="#007AFF">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <style>
        {css}
    </style>
</head>
<body>
    <div class="glass-container" style="margin: 20px; padding: 0; overflow: hidden;">
        <!-- iOS 26 Dynamic Island -->
        <div class="ios-dynamic-island" style="position: absolute; top: 20px; right: 20px; z-index: 1000;">
            <span>📱</span>
            <span>HPNT Manager V2.0</span>
        </div>
        
        <!-- iOS 26 Navigation -->
        <div class="ios-nav">
            <h1 class="ios-nav-title">🚀 HPNT Manager</h1>
            <p style="text-align: center; color: rgba(0,0,0,0.6); margin-top: 8px;">
                💎 iOS 26 스타일 자재관리 시스템
            </p>
        </div>
        
        <!-- Main Content -->
        <div style="padding: 32px;">
            <!-- Quick Actions -->
            <div class="ios-grid ios-grid-2" style="margin-bottom: 32px;">
                <a href="/requests" class="ios-button ios-button-primary ios-haptic ios-fade-in">
                    📋 자재요청 목록
                </a>
                <a href="/add" class="ios-button ios-button-success ios-haptic ios-fade-in">
                    ➕ 새 요청 등록
                </a>
            </div>
            
            <!-- Statistics Cards -->
            <div class="ios-grid ios-grid-4" style="margin-bottom: 32px;">
                <div class="ios-card ios-scale-in">
                    <div style="text-align: center;">
                        <div style="font-size: 32px; font-weight: 700; color: var(--ios-blue); margin-bottom: 8px;">
                            {{ stats.total or 0 }}
                        </div>
                        <div style="color: rgba(0,0,0,0.6); font-weight: 600;">전체 요청</div>
                    </div>
                </div>
                
                <div class="ios-card ios-scale-in">
                    <div style="text-align: center;">
                        <div style="font-size: 32px; font-weight: 700; color: var(--ios-orange); margin-bottom: 8px;">
                            {{ stats.pending or 0 }}
                        </div>
                        <div style="color: rgba(0,0,0,0.6); font-weight: 600;">대기중</div>
                    </div>
                </div>
                
                <div class="ios-card ios-scale-in">
                    <div style="text-align: center;">
                        <div style="font-size: 32px; font-weight: 700; color: var(--ios-green); margin-bottom: 8px;">
                            {{ stats.approved or 0 }}
                        </div>
                        <div style="color: rgba(0,0,0,0.6); font-weight: 600;">승인됨</div>
                    </div>
                </div>
                
                <div class="ios-card ios-scale-in">
                    <div style="text-align: center;">
                        <div style="font-size: 32px; font-weight: 700; color: var(--ios-purple); margin-bottom: 8px;">
                            {{ stats.completed or 0 }}
                        </div>
                        <div style="color: rgba(0,0,0,0.6); font-weight: 600;">완료</div>
                    </div>
                </div>
            </div>
            
            <!-- Feature Cards -->
            <div class="ios-grid ios-grid-3">
                <div class="ios-card ios-fade-in">
                    <div style="text-align: center;">
                        <div style="font-size: 48px; margin-bottom: 16px;">☁️</div>
                        <h3 style="margin-bottom: 12px; color: var(--ios-dark);">iCloud 동기화</h3>
                        <p style="color: rgba(0,0,0,0.6); line-height: 1.5;">
                            모든 Apple 기기에서 실시간 데이터 동기화
                        </p>
                    </div>
                </div>
                
                <div class="ios-card ios-fade-in">
                    <div style="text-align: center;">
                        <div style="font-size: 48px; margin-bottom: 16px;">📱</div>
                        <h3 style="margin-bottom: 12px; color: var(--ios-dark);">iOS 26 최적화</h3>
                        <p style="color: rgba(0,0,0,0.6); line-height: 1.5;">
                            최신 iOS 26 디자인 언어 적용
                        </p>
                    </div>
                </div>
                
                <div class="ios-card ios-fade-in">
                    <div style="text-align: center;">
                        <div style="font-size: 48px; margin-bottom: 16px;">⚡</div>
                        <h3 style="margin-bottom: 12px; color: var(--ios-dark);">경량화 설계</h3>
                        <p style="color: rgba(0,0,0,0.6); line-height: 1.5;">
                            빠르고 가벼운 성능 최적화
                        </p>
                    </div>
                </div>
            </div>
            
            <!-- Environment Info -->
            <div class="ios-card" style="margin-top: 32px; text-align: center;">
                <p style="color: rgba(0,0,0,0.6); margin-bottom: 8px;">
                    🍎 {{ environment }} | 📊 {{ db_location }}
                </p>
                <button onclick="location.reload()" class="ios-button ios-button-glass ios-haptic">
                    🔄 새로고침
                </button>
            </div>
        </div>
    </div>
    
    <script>
        // iOS 26 Haptic Feedback Simulation
        function iosHapticFeedback() {
            if (navigator.vibrate) {
                navigator.vibrate(10);
            }
        }
        
        // Add haptic feedback to all interactive elements
        document.querySelectorAll('.ios-haptic').forEach(element => {
            element.addEventListener('touchstart', iosHapticFeedback);
            element.addEventListener('click', iosHapticFeedback);
        });
        
        // Dynamic Island Animation
        const dynamicIsland = document.querySelector('.ios-dynamic-island');
        if (dynamicIsland) {
            setTimeout(() => {
                dynamicIsland.style.transform = 'scale(0.9)';
                setTimeout(() => {
                    dynamicIsland.style.transform = 'scale(1)';
                }, 200);
            }, 1000);
        }
        
        // Toast Notification System
        function showToast(message, type = 'info') {
            const toast = document.createElement('div');
            toast.className = 'ios-toast';
            toast.textContent = message;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.remove();
            }, 3000);
        }
        
        // Page Load Animation
        document.addEventListener('DOMContentLoaded', function() {
            document.body.style.opacity = '0';
            document.body.style.transition = 'opacity 0.3s ease';
            
            setTimeout(() => {
                document.body.style.opacity = '1';
            }, 100);
        });
    </script>
</body>
</html>
'''
    
    return main_template

def create_ios26_ui_files():
    """iOS 26 UI 파일들 생성"""
    
    # CSS 파일 생성
    css_content = generate_ios26_css()
    with open('static/ios26_design.css', 'w', encoding='utf-8') as f:
        f.write(css_content)
    
    # HTML 템플릿 파일 생성
    main_template = generate_ios26_templates()
    with open('templates/ios26_main.html', 'w', encoding='utf-8') as f:
        f.write(main_template)
    
    # JavaScript 파일 생성
    js_content = '''
// iOS 26 UI Interactions
class iOS26UI {
    constructor() {
        this.init();
    }
    
    init() {
        this.setupHapticFeedback();
        this.setupAnimations();
        this.setupDynamicIsland();
        this.setupToastSystem();
    }
    
    setupHapticFeedback() {
        const hapticElements = document.querySelectorAll('.ios-haptic');
        hapticElements.forEach(element => {
            element.addEventListener('touchstart', () => this.hapticFeedback());
            element.addEventListener('click', () => this.hapticFeedback());
        });
    }
    
    hapticFeedback() {
        if (navigator.vibrate) {
            navigator.vibrate(10);
        }
    }
    
    setupAnimations() {
        // Intersection Observer for scroll animations
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('ios-fade-in');
                }
            });
        });
        
        document.querySelectorAll('.ios-card').forEach(card => {
            observer.observe(card);
        });
    }
    
    setupDynamicIsland() {
        const dynamicIsland = document.querySelector('.ios-dynamic-island');
        if (dynamicIsland) {
            // Dynamic Island expansion animation
            setTimeout(() => {
                dynamicIsland.style.transform = 'scale(0.9)';
                setTimeout(() => {
                    dynamicIsland.style.transform = 'scale(1)';
                }, 200);
            }, 1000);
        }
    }
    
    setupToastSystem() {
        window.showToast = (message, type = 'info') => {
            const toast = document.createElement('div');
            toast.className = 'ios-toast';
            toast.textContent = message;
            
            // Add type-specific styling
            if (type === 'success') {
                toast.style.borderLeft = '4px solid var(--ios-green)';
            } else if (type === 'error') {
                toast.style.borderLeft = '4px solid var(--ios-red)';
            } else if (type === 'warning') {
                toast.style.borderLeft = '4px solid var(--ios-orange)';
            }
            
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.transform = 'translateX(100%)';
                toast.style.opacity = '0';
                setTimeout(() => {
                    toast.remove();
                }, 300);
            }, 3000);
        };
    }
    
    // Form validation with iOS 26 styling
    validateForm(form) {
        const inputs = form.querySelectorAll('input[required], textarea[required]');
        let isValid = true;
        
        inputs.forEach(input => {
            if (!input.value.trim()) {
                this.showInputError(input, '이 필드는 필수입니다.');
                isValid = false;
            } else {
                this.clearInputError(input);
            }
        });
        
        return isValid;
    }
    
    showInputError(input, message) {
        input.style.borderColor = 'var(--ios-red)';
        input.style.boxShadow = '0 0 0 3px rgba(255,59,48,0.1)';
        
        // Show error message
        let errorDiv = input.parentNode.querySelector('.ios-error-message');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'ios-error-message';
            errorDiv.style.color = 'var(--ios-red)';
            errorDiv.style.fontSize = 'var(--font-size-sm)';
            errorDiv.style.marginTop = '4px';
            input.parentNode.appendChild(errorDiv);
        }
        errorDiv.textContent = message;
    }
    
    clearInputError(input) {
        input.style.borderColor = '';
        input.style.boxShadow = '';
        
        const errorDiv = input.parentNode.querySelector('.ios-error-message');
        if (errorDiv) {
            errorDiv.remove();
        }
    }
}

// Initialize iOS 26 UI when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new iOS26UI();
});
'''
    
    with open('static/ios26_ui.js', 'w', encoding='utf-8') as f:
        f.write(js_content)
    
    print("✅ iOS 26 UI 파일들이 성공적으로 생성되었습니다!")
    print("📁 생성된 파일들:")
    print("  - static/ios26_design.css")
    print("  - templates/ios26_main.html")
    print("  - static/ios26_ui.js")

if __name__ == '__main__':
    create_ios26_ui_files() 