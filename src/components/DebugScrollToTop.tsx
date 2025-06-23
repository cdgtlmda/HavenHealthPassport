import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Debug ScrollToTop Component
 * 
 * Temporary component to help debug why footer links don't scroll to top.
 * This adds extensive logging to track what's happening.
 */
export function DebugScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    console.log('=== SCROLL TO TOP DEBUG ===');
    console.log(`Route changed to: ${pathname}`);
    console.log(`Current scroll position: ${window.pageYOffset}px`);
    console.log(`Document height: ${document.documentElement.scrollHeight}px`);
    console.log(`Window height: ${window.innerHeight}px`);
    
    // Track scroll events for a few seconds
    let scrollEventCount = 0;
    const trackScroll = () => {
      scrollEventCount++;
      console.log(`Scroll event ${scrollEventCount}: position ${window.pageYOffset}px`);
    };
    
    window.addEventListener('scroll', trackScroll);
    
    // Stop tracking after 3 seconds
    const stopTracking = setTimeout(() => {
      window.removeEventListener('scroll', trackScroll);
      console.log(`=== Scroll tracking stopped after ${scrollEventCount} events ===`);
    }, 3000);

    // Scroll to top with extensive logging
    const performScroll = () => {
      console.log(`Attempting scroll to top...`);
      console.log(`Before scroll: ${window.pageYOffset}px`);
      
      window.scrollTo({
        top: 0,
        left: 0,
        behavior: 'smooth'
      });
      
      // Check if scroll happened after animation
      setTimeout(() => {
        console.log(`After scroll (1s delay): ${window.pageYOffset}px`);
        if (window.pageYOffset > 50) {
          console.log('⚠️ SCROLL TO TOP FAILED - trying fallback method');
          document.documentElement.scrollTop = 0;
          document.body.scrollTop = 0;
          setTimeout(() => {
            console.log(`After fallback scroll: ${window.pageYOffset}px`);
          }, 500);
        } else {
          console.log('✅ Scroll to top successful');
        }
      }, 1000);
    };

    // Immediate scroll
    performScroll();
    
    // Also try after delay
    const delayedScroll = setTimeout(performScroll, 200);

    return () => {
      clearTimeout(stopTracking);
      clearTimeout(delayedScroll);
      window.removeEventListener('scroll', trackScroll);
    };
  }, [pathname]);

  return null;
}

export default DebugScrollToTop; 