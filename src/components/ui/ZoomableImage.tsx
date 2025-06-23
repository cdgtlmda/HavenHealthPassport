import React, { useState, useRef, useEffect } from 'react';
import { ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ZoomableImageProps {
  src: string;
  alt: string;
  className?: string;
}

const ZoomableImage: React.FC<ZoomableImageProps> = ({ src, alt, className = '' }) => {
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const imageRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleZoomIn = () => {
    setScale(prev => Math.min(prev * 1.5, 5));
  };

  const handleZoomOut = () => {
    setScale(prev => Math.max(prev / 1.5, 0.5));
  };

  const handleReset = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (scale > 1) {
      setIsDragging(true);
      setDragStart({
        x: e.clientX - position.x,
        y: e.clientY - position.y
      });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging && scale > 1) {
      setPosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale(prev => Math.max(0.5, Math.min(5, prev * delta)));
  };

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
    if (!isFullscreen) {
      setScale(1);
      setPosition({ x: 0, y: 0 });
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isFullscreen && e.key === 'Escape') {
        setIsFullscreen(false);
        setScale(1);
        setPosition({ x: 0, y: 0 });
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen]);

  const imageStyle = {
    transform: `scale(${scale}) translate(${position.x / scale}px, ${position.y / scale}px)`,
    cursor: scale > 1 ? (isDragging ? 'grabbing' : 'grab') : 'zoom-in',
    transition: isDragging ? 'none' : 'transform 0.2s ease-out',
  };

  return (
    <>
      <div 
        ref={containerRef}
        className={`relative bg-black border border-white/20 rounded-lg overflow-hidden shadow-lg w-full h-96 md:h-[500px] ${className}`}
      >
        {/* Controls */}
        <div className="absolute top-2 right-2 md:top-4 md:right-4 z-10 flex gap-1 md:gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleZoomIn}
            className="bg-black/90 backdrop-blur-sm text-white border-white/20 text-xs md:text-sm h-8 w-8 md:h-9 md:w-auto md:px-3"
          >
            <ZoomIn className="w-3 h-3 md:w-4 md:h-4" />
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleZoomOut}
            className="bg-black/90 backdrop-blur-sm text-white border-white/20 text-xs md:text-sm h-8 w-8 md:h-9 md:w-auto md:px-3"
          >
            <ZoomOut className="w-3 h-3 md:w-4 md:h-4" />
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleReset}
            className="bg-black/90 backdrop-blur-sm text-white border-white/20 text-xs md:text-sm h-8 w-8 md:h-9 md:w-auto md:px-3"
          >
            <RotateCcw className="w-3 h-3 md:w-4 md:h-4" />
          </Button>
        </div>

        {/* Image Container */}
        <div 
          className="w-full h-full flex items-center justify-center overflow-hidden"
          onWheel={handleWheel}
        >
          <img
            ref={imageRef}
            src={src}
            alt={alt}
            className="max-w-full max-h-full object-contain select-none"
            style={imageStyle}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onClick={scale === 1 ? toggleFullscreen : undefined}
            draggable={false}
          />
        </div>

        {/* Scale indicator */}
        <div className="absolute bottom-2 left-2 md:bottom-4 md:left-4 bg-black/70 text-white px-2 py-1 rounded text-xs md:text-sm">
          {Math.round(scale * 100)}%
        </div>
      </div>

      {/* Fullscreen Modal */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-2 md:p-4">
          <div className="relative w-full h-full max-w-7xl max-h-full">
            {/* Fullscreen Controls */}
            <div className="absolute top-2 right-2 md:top-4 md:right-4 z-10 flex gap-1 md:gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={handleZoomIn}
                className="bg-black/90 backdrop-blur-sm text-white border-white/20 text-xs md:text-sm h-8 w-8 md:h-9 md:w-auto md:px-3"
              >
                <ZoomIn className="w-3 h-3 md:w-4 md:h-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleZoomOut}
                className="bg-black/90 backdrop-blur-sm text-white border-white/20 text-xs md:text-sm h-8 w-8 md:h-9 md:w-auto md:px-3"
              >
                <ZoomOut className="w-3 h-3 md:w-4 md:h-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleReset}
                className="bg-black/90 backdrop-blur-sm text-white border-white/20 text-xs md:text-sm h-8 w-8 md:h-9 md:w-auto md:px-3"
              >
                <RotateCcw className="w-3 h-3 md:w-4 md:h-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setIsFullscreen(false)}
                className="bg-black/90 backdrop-blur-sm text-white border-white/20 text-xs md:text-sm h-8 w-8 md:h-9 md:w-auto md:px-3"
              >
                ✕
              </Button>
            </div>

            <div 
              className="w-full h-full flex items-center justify-center overflow-hidden"
              onWheel={handleWheel}
            >
              <img
                src={src}
                alt={alt}
                className="max-w-full max-h-full object-contain select-none"
                style={imageStyle}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                draggable={false}
              />
            </div>

            {/* Fullscreen Scale indicator */}
            <div className="absolute bottom-2 left-2 md:bottom-4 md:left-4 bg-black/70 text-white px-2 py-1 rounded text-xs md:text-sm">
              {Math.round(scale * 100)}% • Press ESC to close
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ZoomableImage; 