import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  FlatList,
  ScrollView,
  View,
  ViewabilityConfig,
  ViewToken,
  NativeScrollEvent,
  NativeSyntheticEvent,
  LayoutChangeEvent,
} from 'react-native';

interface VirtualScrollConfig {
  itemHeight?: number | ((index: number) => number);
  overscan: number;
  initialScrollIndex?: number;
  scrollEventThrottle: number;
  windowSize: number;
  maxToRenderPerBatch: number;
  updateCellsBatchingPeriod: number;
  removeClippedSubviews: boolean;
  enableMemoryOptimization: boolean;
}

interface VirtualScrollProps<T> {
  data: T[];
  renderItem: (item: T, index: number) => React.ReactElement;
  keyExtractor: (item: T, index: number) => string;
  onEndReached?: () => void;
  onEndReachedThreshold?: number;
  onViewableItemsChanged?: (info: { viewableItems: ViewToken[]; changed: ViewToken[] }) => void;
  config?: Partial<VirtualScrollConfig>;
  ListHeaderComponent?: React.ReactElement;
  ListFooterComponent?: React.ReactElement;
  ListEmptyComponent?: React.ReactElement;
}

export function VirtualScroll<T>({
  data,
  renderItem,
  keyExtractor,
  onEndReached,
  onEndReachedThreshold = 0.1,
  onViewableItemsChanged,
  config = {},
  ListHeaderComponent,
  ListFooterComponent,
  ListEmptyComponent,
}: VirtualScrollProps<T>) {
  const scrollConfig: VirtualScrollConfig = {
    overscan: 3,
    scrollEventThrottle: 16,
    windowSize: 10,
    maxToRenderPerBatch: 10,
    updateCellsBatchingPeriod: 50,
    removeClippedSubviews: true,
    enableMemoryOptimization: true,
    ...config,
  };

  const flatListRef = useRef<FlatList<T>>(null);
  const [visibleRange, setVisibleRange] = useState({ start: 0, end: 10 });
  const itemHeights = useRef<Map<number, number>>(new Map());
  const scrollOffset = useRef(0);
  const containerHeight = useRef(0);

  // Calculate which items should be rendered
  const itemsToRender = useMemo(() => {
    const startIndex = Math.max(0, visibleRange.start - scrollConfig.overscan);
    const endIndex = Math.min(
      data.length - 1,
      visibleRange.end + scrollConfig.overscan
    );

    return data.slice(startIndex, endIndex + 1).map((item, idx) => ({
      item,
      originalIndex: startIndex + idx,
    }));
  }, [data, visibleRange, scrollConfig.overscan]);

  // Handle scroll events
  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const offset = event.nativeEvent.contentOffset.y;
      scrollOffset.current = offset;

      // Calculate visible range based on scroll position
      const { start, end } = calculateVisibleRange(
        offset,
        containerHeight.current,
        itemHeights.current,
        scrollConfig.itemHeight
      );

      setVisibleRange({ start, end });

      // Check if end reached
      const contentHeight = event.nativeEvent.contentSize.height;
      const scrollHeight = event.nativeEvent.layoutMeasurement.height;
      const isEndReached =
        offset + scrollHeight >= contentHeight - scrollHeight * onEndReachedThreshold;

      if (isEndReached && onEndReached) {
        onEndReached();
      }
    },
    [scrollConfig.itemHeight, onEndReachedThreshold, onEndReached]
  );

  // Handle layout changes
  const handleLayout = useCallback((event: LayoutChangeEvent) => {
    containerHeight.current = event.nativeEvent.layout.height;
  }, []);

  // Handle item layout
  const handleItemLayout = useCallback(
    (index: number) => (event: LayoutChangeEvent) => {
      const height = event.nativeEvent.layout.height;
      itemHeights.current.set(index, height);
    },
    []
  );

  // Viewability config
  const viewabilityConfig: ViewabilityConfig = {
    minimumViewTime: 250,
    viewAreaCoveragePercentThreshold: 50,
    waitForInteraction: false,
  };

  // Render item wrapper
  const renderItemWrapper = useCallback(
    ({ item, index }: { item: { item: T; originalIndex: number }; index: number }) => {
      const { item: actualItem, originalIndex } = item;
      
      return (
        <View
          key={keyExtractor(actualItem, originalIndex)}
          onLayout={handleItemLayout(originalIndex)}
        >
          {renderItem(actualItem, originalIndex)}
        </View>
      );
    },
    [renderItem, keyExtractor, handleItemLayout]
  );

  // Get item layout (for fixed height items)
  const getItemLayout = useCallback(
    (data: any, index: number) => {
      if (typeof scrollConfig.itemHeight === 'number') {
        return {
          length: scrollConfig.itemHeight,
          offset: scrollConfig.itemHeight * index,
          index,
        };
      }
      return undefined;
    },
    [scrollConfig.itemHeight]
  );

  if (!data || data.length === 0) {
    return ListEmptyComponent || null;
  }

  return (
    <FlatList
      ref={flatListRef}
      data={itemsToRender}
      renderItem={renderItemWrapper}
      keyExtractor={(item, index) => keyExtractor(item.item, item.originalIndex)}
      onScroll={handleScroll}
      onLayout={handleLayout}
      scrollEventThrottle={scrollConfig.scrollEventThrottle}
      windowSize={scrollConfig.windowSize}
      maxToRenderPerBatch={scrollConfig.maxToRenderPerBatch}
      updateCellsBatchingPeriod={scrollConfig.updateCellsBatchingPeriod}
      removeClippedSubviews={scrollConfig.removeClippedSubviews}
      initialNumToRender={scrollConfig.windowSize}
      getItemLayout={getItemLayout}
      viewabilityConfig={viewabilityConfig}
      onViewableItemsChanged={onViewableItemsChanged}
      ListHeaderComponent={ListHeaderComponent}
      ListFooterComponent={ListFooterComponent}
    />
  );
}

// Calculate visible range based on scroll position
function calculateVisibleRange(
  scrollOffset: number,
  containerHeight: number,
  itemHeights: Map<number, number>,
  itemHeight?: number | ((index: number) => number)
): { start: number; end: number } {
  if (typeof itemHeight === 'number') {
    // Fixed height items
    const start = Math.floor(scrollOffset / itemHeight);
    const end = Math.ceil((scrollOffset + containerHeight) / itemHeight);
    return { start, end };
  }

  // Variable height items
  let currentOffset = 0;
  let start = -1;
  let end = -1;

  for (let i = 0; i < 1000; i++) { // Reasonable upper limit
    const height = itemHeights.get(i) || 
      (typeof itemHeight === 'function' ? itemHeight(i) : 100); // Default height

    if (start === -1 && currentOffset + height > scrollOffset) {
      start = i;
    }

    if (currentOffset > scrollOffset + containerHeight) {
      end = i;
      break;
    }

    currentOffset += height;
  }

  return {
    start: Math.max(0, start),
    end: Math.max(0, end),
  };
}

// Hook for managing virtual scroll state
export function useVirtualScroll<T>(
  data: T[],
  config?: Partial<VirtualScrollConfig>
) {
  const [metrics, setMetrics] = useState({
    renderedItems: 0,
    totalItems: data.length,
    memoryUsage: 0,
  });

  useEffect(() => {
    // Calculate approximate memory usage
    const itemSize = 1024; // Approximate bytes per item
    const renderedItems = Math.min(
      data.length,
      (config?.windowSize || 10) + (config?.overscan || 3) * 2
    );
    const memoryUsage = renderedItems * itemSize;

    setMetrics({
      renderedItems,
      totalItems: data.length,
      memoryUsage,
    });
  }, [data.length, config]);

  return { metrics };
}

export default VirtualScroll;