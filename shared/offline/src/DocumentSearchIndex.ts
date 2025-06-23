import { EventEmitter } from 'events';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ValidationUtils } from './ValidationUtils';

interface SearchableDocument {
  id: string;
  title: string;
  content: string;
  type: string;
  tags: string[];
  createdAt: number;
  updatedAt: number;
  metadata?: Record<string, any>;
}

interface SearchIndex {
  terms: Map<string, Set<string>>; // term -> document IDs
  documents: Map<string, SearchableDocument>;
  documentTerms: Map<string, Set<string>>; // document ID -> terms
}

interface SearchResult {
  documentId: string;
  document: SearchableDocument;
  score: number;
  highlights: Array<{
    field: string;
    snippets: string[];
  }>;
}

interface SearchOptions {
  fuzzy?: boolean;
  maxResults?: number;
  filters?: {
    type?: string[];
    tags?: string[];
    dateRange?: { start: number; end: number };
  };
  highlightLength?: number;
}

export class DocumentSearchIndex extends EventEmitter {
  private static readonly INDEX_KEY = '@document_search_index';
  private static readonly STOPWORDS = new Set([
    'the', 'is', 'at', 'which', 'on', 'a', 'an', 'as', 'are', 'was', 'were',
    'be', 'have', 'has', 'had', 'being', 'having', 'with', 'they', 'them',
    'for', 'of', 'to', 'from', 'in', 'out', 'up', 'down', 'and', 'or', 'but',
  ]);
  
  private index: SearchIndex;
  private isLoaded = false;
  
  constructor() {
    super();
    this.index = {
      terms: new Map(),
      documents: new Map(),
      documentTerms: new Map(),
    };
  }

  /**
   * Initialize search index
   */
  async initialize(): Promise<void> {
    try {
      await this.loadIndex();
      this.isLoaded = true;
      this.emit('index-loaded');
    } catch (error) {
      console.error('Failed to load search index:', error);
      this.emit('index-error', error);
    }
  }

  /**
   * Add document to index
   */
  async addDocument(document: SearchableDocument): Promise<void> {
    if (!this.isLoaded) {
      await this.initialize();
    }
    
    // Remove existing document if updating
    if (this.index.documents.has(document.id)) {
      await this.removeDocument(document.id);
    }
    
    // Extract and normalize terms
    const terms = this.extractTerms(document);
    
    // Add to index
    this.index.documents.set(document.id, document);
    this.index.documentTerms.set(document.id, new Set(terms));
    
    // Update inverted index
    for (const term of terms) {
      if (!this.index.terms.has(term)) {
        this.index.terms.set(term, new Set());
      }
      this.index.terms.get(term)!.add(document.id);
    }
    
    // Save index
    await this.saveIndex();
    
    this.emit('document-indexed', { documentId: document.id });
  }

  /**
   * Search documents
   */
  async search(query: string, options: SearchOptions = {}): Promise<SearchResult[]> {
    if (!this.isLoaded) {
      await this.initialize();
    }
    
    const {
      fuzzy = false,
      maxResults = 20,
      filters,
      highlightLength = 100,
    } = options;
    
    // Extract query terms
    const queryTerms = this.normalizeText(query).split(/\s+/);
    
    // Find matching documents
    const documentScores = new Map<string, number>();
    
    for (const term of queryTerms) {
      const matchingTerms = fuzzy 
        ? this.findFuzzyMatches(term)
        : [term];
      
      for (const matchTerm of matchingTerms) {
        const documentIds = this.index.terms.get(matchTerm);
        if (documentIds) {
          for (const docId of documentIds) {
            const currentScore = documentScores.get(docId) || 0;
            const termFrequency = this.calculateTermFrequency(docId, matchTerm);
            const idf = this.calculateIDF(matchTerm);
            documentScores.set(docId, currentScore + (termFrequency * idf));
          }
        }
      }
    }
    
    // Apply filters
    let results = Array.from(documentScores.entries())
      .map(([docId, score]) => ({
        documentId: docId,
        document: this.index.documents.get(docId)!,
        score,
      }))
      .filter(result => this.applyFilters(result.document, filters));
    
    // Sort by score
    results.sort((a, b) => b.score - a.score);
    
    // Limit results
    results = results.slice(0, maxResults);
    
    // Generate highlights
    const searchResults: SearchResult[] = results.map(result => ({
      ...result,
      highlights: this.generateHighlights(result.document, queryTerms, highlightLength),
    }));
    
    this.emit('search-completed', { query, resultCount: searchResults.length });
    return searchResults;
  }

  /**
   * Remove document from index
   */
  async removeDocument(documentId: string): Promise<void> {
    const terms = this.index.documentTerms.get(documentId);
    if (!terms) return;
    
    // Remove from inverted index
    for (const term of terms) {
      const documentIds = this.index.terms.get(term);
      if (documentIds) {
        documentIds.delete(documentId);
        if (documentIds.size === 0) {
          this.index.terms.delete(term);
        }
      }
    }
    
    // Remove document
    this.index.documents.delete(documentId);
    this.index.documentTerms.delete(documentId);
    
    await this.saveIndex();
    this.emit('document-removed', { documentId });
  }

  /**
   * Update document
   */
  async updateDocument(document: SearchableDocument): Promise<void> {
    await this.addDocument(document);
  }

  /**
   * Get index statistics
   */
  getStatistics(): {
    documentCount: number;
    termCount: number;
    averageTermsPerDocument: number;
  } {
    const documentCount = this.index.documents.size;
    const termCount = this.index.terms.size;
    
    let totalTerms = 0;
    for (const terms of this.index.documentTerms.values()) {
      totalTerms += terms.size;
    }
    
    return {
      documentCount,
      termCount,
      averageTermsPerDocument: documentCount > 0 ? totalTerms / documentCount : 0,
    };
  }

  /**
   * Clear index
   */
  async clearIndex(): Promise<void> {
    this.index = {
      terms: new Map(),
      documents: new Map(),
      documentTerms: new Map(),
    };
    
    await AsyncStorage.removeItem(DocumentSearchIndex.INDEX_KEY);
    this.emit('index-cleared');
  }

  /**
   * Private helper methods
   */
  
  private extractTerms(document: SearchableDocument): string[] {
    const terms = new Set<string>();
    
    // Extract from content
    const contentTerms = this.normalizeText(document.content).split(/\s+/);
    contentTerms.forEach(term => {
      if (term.length > 2 && !DocumentSearchIndex.STOPWORDS.has(term)) {
        terms.add(term);
      }
    });
    
    // Extract from title (weighted higher)
    const titleTerms = this.normalizeText(document.title).split(/\s+/);
    titleTerms.forEach(term => {
      if (term.length > 2 && !DocumentSearchIndex.STOPWORDS.has(term)) {
        terms.add(term);
        // Add twice for higher weight
        terms.add(term);
      }
    });
    
    // Add tags
    document.tags.forEach(tag => {
      terms.add(this.normalizeText(tag));
    });
    
    // Extract from metadata
    if (document.metadata) {
      Object.values(document.metadata).forEach(value => {
        if (typeof value === 'string') {
          const metaTerms = this.normalizeText(value).split(/\s+/);
          metaTerms.forEach(term => {
            if (term.length > 2 && !DocumentSearchIndex.STOPWORDS.has(term)) {
              terms.add(term);
            }
          });
        }
      });
    }
    
    return Array.from(terms);
  }

  private normalizeText(text: string): string {
    return text
      .toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  private calculateTermFrequency(documentId: string, term: string): number {
    const documentTerms = this.index.documentTerms.get(documentId);
    if (!documentTerms) return 0;
    
    let count = 0;
    for (const docTerm of documentTerms) {
      if (docTerm === term) count++;
    }
    
    return count / documentTerms.size;
  }

  private calculateIDF(term: string): number {
    const documentCount = this.index.documents.size;
    const documentsWithTerm = this.index.terms.get(term)?.size || 0;
    
    if (documentsWithTerm === 0) return 0;
    
    return Math.log(documentCount / documentsWithTerm);
  }

  private findFuzzyMatches(term: string): string[] {
    const matches: string[] = [];
    const maxDistance = Math.floor(term.length / 3);
    
    for (const indexTerm of this.index.terms.keys()) {
      if (this.levenshteinDistance(term, indexTerm) <= maxDistance) {
        matches.push(indexTerm);
      }
    }
    
    return matches;
  }

  private levenshteinDistance(a: string, b: string): number {
    const matrix: number[][] = [];
    
    for (let i = 0; i <= b.length; i++) {
      matrix[i] = [i];
    }
    
    for (let j = 0; j <= a.length; j++) {
      matrix[0][j] = j;
    }
    
    for (let i = 1; i <= b.length; i++) {
      for (let j = 1; j <= a.length; j++) {
        if (b.charAt(i - 1) === a.charAt(j - 1)) {
          matrix[i][j] = matrix[i - 1][j - 1];
        } else {
          matrix[i][j] = Math.min(
            matrix[i - 1][j - 1] + 1,
            matrix[i][j - 1] + 1,
            matrix[i - 1][j] + 1
          );
        }
      }
    }
    
    return matrix[b.length][a.length];
  }

  private applyFilters(
    document: SearchableDocument,
    filters?: SearchOptions['filters']
  ): boolean {
    if (!filters) return true;
    
    if (filters.type && !filters.type.includes(document.type)) {
      return false;
    }
    
    if (filters.tags) {
      const hasMatchingTag = filters.tags.some(tag => 
        document.tags.includes(tag)
      );
      if (!hasMatchingTag) return false;
    }
    
    if (filters.dateRange) {
      if (document.createdAt < filters.dateRange.start ||
          document.createdAt > filters.dateRange.end) {
        return false;
      }
    }
    
    return true;
  }

  private generateHighlights(
    document: SearchableDocument,
    queryTerms: string[],
    maxLength: number
  ): Array<{ field: string; snippets: string[] }> {
    const highlights: Array<{ field: string; snippets: string[] }> = [];
    
    // Highlight in content
    const contentSnippets = this.findSnippets(
      document.content,
      queryTerms,
      maxLength
    );
    if (contentSnippets.length > 0) {
      highlights.push({ field: 'content', snippets: contentSnippets });
    }
    
    // Highlight in title
    if (queryTerms.some(term => 
      document.title.toLowerCase().includes(term.toLowerCase())
    )) {
      highlights.push({ field: 'title', snippets: [document.title] });
    }
    
    return highlights;
  }

  private findSnippets(
    text: string,
    terms: string[],
    maxLength: number
  ): string[] {
    const snippets: string[] = [];
    const lowerText = text.toLowerCase();
    
    for (const term of terms) {
      const index = lowerText.indexOf(term.toLowerCase());
      if (index !== -1) {
        const start = Math.max(0, index - Math.floor(maxLength / 2));
        const end = Math.min(text.length, index + term.length + Math.floor(maxLength / 2));
        
        let snippet = text.substring(start, end);
        if (start > 0) snippet = '...' + snippet;
        if (end < text.length) snippet = snippet + '...';
        
        snippets.push(snippet);
      }
    }
    
    return snippets;
  }

  private async loadIndex(): Promise<void> {
    try {
      const stored = await AsyncStorage.getItem(DocumentSearchIndex.INDEX_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        
        // Reconstruct Maps from stored data
        this.index.terms = new Map(
          Object.entries(parsed.terms).map(([term, docIds]) => 
            [term, new Set(docIds as string[])]
          )
        );
        
        this.index.documents = new Map(
          Object.entries(parsed.documents)
        );
        
        this.index.documentTerms = new Map(
          Object.entries(parsed.documentTerms).map(([docId, terms]) => 
            [docId, new Set(terms as string[])]
          )
        );
      }
    } catch (error) {
      console.error('Failed to load search index:', error);
    }
  }

  private async saveIndex(): Promise<void> {
    try {
      const serializable = {
        terms: Object.fromEntries(
          Array.from(this.index.terms.entries()).map(([term, docIds]) => 
            [term, Array.from(docIds)]
          )
        ),
        documents: Object.fromEntries(this.index.documents),
        documentTerms: Object.fromEntries(
          Array.from(this.index.documentTerms.entries()).map(([docId, terms]) => 
            [docId, Array.from(terms)]
          )
        ),
      };
      
      await AsyncStorage.setItem(
        DocumentSearchIndex.INDEX_KEY,
        JSON.stringify(serializable)
      );
    } catch (error) {
      console.error('Failed to save search index:', error);
      throw error;
    }
  }
}

export default DocumentSearchIndex;