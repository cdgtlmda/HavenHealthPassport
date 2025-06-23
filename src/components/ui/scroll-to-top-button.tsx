import { useState, useEffect } from 'react';
import { ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useScrollToTop } from '@/hooks/use-scroll-to-top';
import { cn } from '@/lib/utils';

interface ScrollToTopButtonProps {
  showAfter?: number; // Show button after scrolling this many pixels
  className?: string;
}

/**
 * Floating Scroll to Top Button
 * 
 * A floating button that appears when the user scrolls down and allows
 * them to quickly return to the top of the page. Great for long pages
 * like landing pages, documentation, or content-heavy sections.
 */
export function ScrollToTopButton({ showAfter = 300, className }: ScrollToTopButtonProps) {
  const [isVisible, setIsVisible] = useState(false);
  const scrollToTop = useScrollToTop();

  useEffect(() => {
    const toggleVisibility = () => {
      if (window.pageYOffset > showAfter) {
        setIsVisible(true);
      } else {
        setIsVisible(false);
      }
    };

    window.addEventListener('scroll', toggleVisibility);
    return () => window.removeEventListener('scroll', toggleVisibility);
  }, [showAfter]);

  if (!isVisible) {
    return null;
  }

  return (
    <Button
      onClick={() => scrollToTop(true)}
      size="icon"
      className={cn(
        "fixed bottom-4 right-4 z-50 rounded-full shadow-lg",
        "bg-primary hover:bg-primary/90 text-primary-foreground",
        "transition-all duration-300 ease-in-out",
        "hover:scale-110 active:scale-95",
        className
      )}
      aria-label="Scroll to top"
    >
      <ChevronUp className="h-4 w-4" />
    </Button>
  );
}

export default ScrollToTopButton; 