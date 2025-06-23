import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

interface ScrollToTopProps {
  smooth?: boolean;
}

/**
 * ScrollToTop Component
 * 
 * Automatically scrolls to the top of the page when the route changes.
 * This provides better UX by ensuring users always see the top of new pages
 * when navigating via navigation menus or footer links.
 * 
 * @param smooth - Whether to use smooth scrolling animation (default: true for better UX)
 */
export function ScrollToTop({ smooth = true }: ScrollToTopProps = {}) {
  const { pathname } = useLocation();

  useEffect(() => {
    // Scroll to top when route changes
    console.log(`ScrollToTop: Navigating to ${pathname}, current scroll: ${window.pageYOffset}`);
    
    // Multiple scroll methods to ensure it works
    const scrollToTopNow = () => {
      // Method 1: Modern scrollTo with behavior
      window.scrollTo({
        top: 0,
        left: 0,
        behavior: smooth ? 'smooth' : 'instant'
      });
      
      // Method 2: Fallback for older browsers
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
      
      console.log(`ScrollToTop: Scrolled to top for ${pathname}, new scroll: ${window.pageYOffset}`);
    };

    // Immediate scroll
    scrollToTopNow();
    
    // Also scroll after a short delay to ensure page has rendered
    const scrollTimeout = setTimeout(scrollToTopNow, 100);

    return () => clearTimeout(scrollTimeout);
  }, [pathname, smooth]);

  return null; // This component doesn't render anything
}

export default ScrollToTop; 