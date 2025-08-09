
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
