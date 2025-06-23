import { useCallback } from 'react';

/**
 * Hook for manually scrolling to top
 * 
 * Useful for buttons, actions, or other components that need to 
 * programmatically scroll to the top of the page.
 * 
 * @returns scrollToTop function that can be called anywhere
 */
export function useScrollToTop() {
  const scrollToTop = useCallback((smooth: boolean = true) => {
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: smooth ? 'smooth' : 'instant'
    });
  }, []);

  return scrollToTop;
}

export default useScrollToTop; 