// Pattern 5 from nfr-design.md
// Lazy load via IntersectionObserver — NFR-MD0-P4
// placeholder grey until loaded; fade-in with opacity
// NEVER dangerouslySetInnerHTML (NFR-MD0-S7)

import { useState, useRef, useEffect } from 'react';

function useInView(ref: React.RefObject<HTMLElement | null>): boolean {
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect(); // load once
        }
      },
      { rootMargin: '100px' }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);

  return inView;
}

interface ScreenshotThumbnailProps {
  url: string; // relative path, e.g. run_id/profile/flow/step-state.png
  alt: string;
}

export function ScreenshotThumbnail({ url, alt }: ScreenshotThumbnailProps) {
  const [loaded, setLoaded] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inView = useInView(containerRef);

  // Construct /v1/screenshots/... (relative, same origin — proxied by Vite/FastAPI)
  const src = `/v1/screenshots/${url}`;

  return (
    <div
      ref={containerRef}
      className="aspect-video bg-gray-200 rounded overflow-hidden"
      style={{ minHeight: '80px' }}
    >
      {inView && (
        <img
          src={src}
          alt={alt}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          className={['w-full h-full object-cover transition-opacity duration-300', loaded ? 'opacity-100' : 'opacity-0'].join(' ')}
        />
      )}
    </div>
  );
}
