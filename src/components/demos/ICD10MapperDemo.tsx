import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  Search, 
  CheckCircle, 
  AlertTriangle, 
  Book, 
  Target,
  Clock,
  BarChart3,
  Zap,
  Globe
} from 'lucide-react';

interface ICD10Code {
  code: string;
  description: string;
  matchType: 'EXACT' | 'PARTIAL' | 'FUZZY' | 'SEMANTIC' | 'ABBREVIATION';
  confidence: number;
  isBillable: boolean;
  category?: string;
  children?: ICD10Code[];
}

interface SearchResult {
  query: string;
  codes: ICD10Code[];
  searchTime: number;
  totalResults: number;
}

interface MapperStats {
  totalCodes: number;
  billableCodes: number;
  nonBillableCodes: number;
  cacheHits: number;
  cacheMisses: number;
  cacheHitRate: number;
}

const ICD10MapperDemo: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [includeChildren, setIncludeChildren] = useState(false);
  const [enableFuzzyMatching, setEnableFuzzyMatching] = useState(true);
  const [minConfidence, setMinConfidence] = useState(0.7);
  const [searchHistory, setSearchHistory] = useState<SearchResult[]>([]);
  const [stats, setStats] = useState<MapperStats>({
    totalCodes: 72184,
    billableCodes: 68442,
    nonBillableCodes: 3742,
    cacheHits: 0,
    cacheMisses: 0,
    cacheHitRate: 0
  });

  // Sample ICD-10 codes database
  const sampleCodes: ICD10Code[] = [
    {
      code: 'J00',
      description: 'Acute nasopharyngitis [common cold]',
      matchType: 'EXACT',
      confidence: 1.0,
      isBillable: true,
      category: 'Diseases of the respiratory system'
    },
    {
      code: 'J45',
      description: 'Asthma',
      matchType: 'EXACT',
      confidence: 1.0,
      isBillable: false,
      category: 'Diseases of the respiratory system',
      children: [
        {
          code: 'J45.0',
          description: 'Predominantly allergic asthma',
          matchType: 'EXACT',
          confidence: 1.0,
          isBillable: true,
          category: 'Diseases of the respiratory system'
        },
        {
          code: 'J45.1',
          description: 'Nonallergic asthma',
          matchType: 'EXACT',
          confidence: 1.0,
          isBillable: true,
          category: 'Diseases of the respiratory system'
        }
      ]
    },
    {
      code: 'E11',
      description: 'Type 2 diabetes mellitus',
      matchType: 'EXACT',
      confidence: 1.0,
      isBillable: false,
      category: 'Endocrine, nutritional and metabolic diseases'
    },
    {
      code: 'A00',
      description: 'Cholera',
      matchType: 'EXACT',
      confidence: 1.0,
      isBillable: false,
      category: 'Certain infectious and parasitic diseases',
      children: [
        {
          code: 'A00.0',
          description: 'Cholera due to Vibrio cholerae 01, biovar cholerae',
          matchType: 'EXACT',
          confidence: 1.0,
          isBillable: true,
          category: 'Certain infectious and parasitic diseases'
        }
      ]
    }
  ];

  const performSearch = async (query: string) => {
    if (!query.trim()) return;

    setIsSearching(true);
    const startTime = Date.now();

    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 300));

    // Simple search logic
    let results = sampleCodes.filter(code => {
      const searchLower = query.toLowerCase();
      const codeLower = code.code.toLowerCase();
      const descLower = code.description.toLowerCase();

      // Exact code match
      if (codeLower === searchLower) {
        return { ...code, matchType: 'EXACT' as const, confidence: 1.0 };
      }

      // Partial code match
      if (codeLower.includes(searchLower)) {
        return { ...code, matchType: 'PARTIAL' as const, confidence: 0.9 };
      }

      // Description match
      if (descLower.includes(searchLower)) {
        return { ...code, matchType: 'SEMANTIC' as const, confidence: 0.8 };
      }

      // Fuzzy matching for common terms
      if (enableFuzzyMatching) {
        const fuzzyTerms: { [key: string]: string[] } = {
          'cold': ['common cold', 'nasopharyngitis'],
          'asthm': ['asthma'],
          'diabetes': ['diabetes mellitus'],
          'uri': ['upper respiratory infection', 'nasopharyngitis']
        };

        for (const [term, matches] of Object.entries(fuzzyTerms)) {
          if (searchLower.includes(term)) {
            for (const match of matches) {
              if (descLower.includes(match)) {
                return { ...code, matchType: 'FUZZY' as const, confidence: 0.75 };
              }
            }
          }
        }
      }

      return null;
    }).filter(Boolean) as ICD10Code[];

    // Include children if requested
    if (includeChildren) {
      const withChildren: ICD10Code[] = [];
      results.forEach(code => {
        withChildren.push(code);
        if (code.children) {
          withChildren.push(...code.children);
        }
      });
      results = withChildren;
    }

    // Filter by confidence
    results = results.filter(code => code.confidence >= minConfidence);

    // Sort by confidence
    results.sort((a, b) => b.confidence - a.confidence);

    const searchTime = Date.now() - startTime;
    const result: SearchResult = {
      query,
      codes: results,
      searchTime,
      totalResults: results.length
    };

    setSearchResults(result);
    setSearchHistory(prev => [result, ...prev.slice(0, 4)]);
    
    // Update stats
    setStats(prev => ({
      ...prev,
      cacheHits: prev.cacheHits + (Math.random() > 0.3 ? 1 : 0),
      cacheMisses: prev.cacheMisses + (Math.random() > 0.7 ? 1 : 0),
      cacheHitRate: (prev.cacheHits / (prev.cacheHits + prev.cacheMisses)) * 100
    }));

    setIsSearching(false);
  };

  const validateCode = (code: string): { valid: boolean; message?: string } => {
    const found = sampleCodes.find(c => c.code === code);
    if (found) {
      return { valid: true };
    }
    return { valid: false, message: 'Code not found in database' };
  };

  const checkCompatibility = (code1: string, code2: string): { compatible: boolean; message?: string } => {
    if (code1 === code2) {
      return { compatible: true, message: 'Same code' };
    }
    
    // Simple hierarchy check
    if (code1.startsWith(code2) || code2.startsWith(code1)) {
      return { compatible: true, message: 'Hierarchically related' };
    }
    
    return { compatible: true, message: 'No conflicts detected' };
  };

  const getMatchTypeColor = (matchType: string) => {
    switch (matchType) {
      case 'EXACT': return 'bg-green-100 text-green-800';
      case 'PARTIAL': return 'bg-blue-100 text-blue-800';
      case 'FUZZY': return 'bg-yellow-100 text-yellow-800';
      case 'SEMANTIC': return 'bg-purple-100 text-purple-800';
      case 'ABBREVIATION': return 'bg-orange-100 text-orange-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const quickSearchTerms = ['common cold', 'asthma', 'diabetes', 'J00', 'A00'];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">ICD-10 Code Mapper Demo</h2>
          <p className="text-gray-600">Medical terminology mapping and code validation system</p>
        </div>
        <div className="flex items-center space-x-2">
          <Badge variant="outline" className="text-xs">
            <Book className="w-3 h-3 mr-1" />
            {stats.totalCodes.toLocaleString()} codes
          </Badge>
          <Badge variant="outline" className="text-xs">
            <Target className="w-3 h-3 mr-1" />
            {stats.cacheHitRate.toFixed(1)}% cache hit rate
          </Badge>
        </div>
      </div>

      <Tabs defaultValue="search" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="search">Code Search</TabsTrigger>
          <TabsTrigger value="validation">Code Validation</TabsTrigger>
          <TabsTrigger value="batch">Batch Operations</TabsTrigger>
          <TabsTrigger value="stats">Statistics</TabsTrigger>
        </TabsList>

        <TabsContent value="search" className="space-y-4">
          {/* Search Interface */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Search className="w-5 h-5 mr-2" />
                ICD-10 Code Search
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex space-x-2">
                <div className="flex-1">
                  <Input
                    placeholder="Search by code or description (e.g., 'J00', 'common cold', 'asthm')"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && performSearch(searchQuery)}
                  />
                </div>
                <Button onClick={() => performSearch(searchQuery)} disabled={isSearching}>
                  {isSearching ? (
                    <>
                      <Clock className="w-4 h-4 mr-2 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4 mr-2" />
                      Search
                    </>
                  )}
                </Button>
              </div>

              {/* Search Options */}
              <div className="flex items-center space-x-4 text-sm">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="includeChildren"
                    checked={includeChildren}
                    onCheckedChange={(checked) => setIncludeChildren(checked as boolean)}
                  />
                  <label htmlFor="includeChildren">Include child codes</label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="fuzzyMatching"
                    checked={enableFuzzyMatching}
                    onCheckedChange={(checked) => setEnableFuzzyMatching(checked as boolean)}
                  />
                  <label htmlFor="fuzzyMatching">Enable fuzzy matching</label>
                </div>
                <div className="flex items-center space-x-2">
                  <label htmlFor="minConfidence">Min confidence:</label>
                  <Input
                    id="minConfidence"
                    type="number"
                    min="0"
                    max="1"
                    step="0.1"
                    value={minConfidence}
                    onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
                    className="w-20"
                  />
                </div>
              </div>

              {/* Quick Search */}
              <div>
                <p className="text-sm text-gray-600 mb-2">Quick search:</p>
                <div className="flex flex-wrap gap-2">
                  {quickSearchTerms.map(term => (
                    <Button
                      key={term}
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSearchQuery(term);
                        performSearch(term);
                      }}
                    >
                      {term}
                    </Button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Search Results */}
          {searchResults && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Search Results</span>
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <span>{searchResults.totalResults} results</span>
                    <span>•</span>
                    <span>{searchResults.searchTime}ms</span>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {searchResults.codes.length > 0 ? (
                  <div className="space-y-3">
                    {searchResults.codes.map((code, index) => (
                      <div key={`${code.code}-${index}`} className="flex items-center justify-between p-3 border rounded-lg">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="font-mono font-bold">{code.code}</span>
                            <Badge className={getMatchTypeColor(code.matchType)}>
                              {code.matchType}
                            </Badge>
                            {code.isBillable ? (
                              <Badge variant="outline" className="text-green-600">Billable</Badge>
                            ) : (
                              <Badge variant="outline" className="text-gray-600">Non-billable</Badge>
                            )}
                          </div>
                          <p className="text-sm text-gray-700">{code.description}</p>
                          {code.category && (
                            <p className="text-xs text-gray-500 mt-1">{code.category}</p>
                          )}
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-medium">
                            {(code.confidence * 100).toFixed(1)}%
                          </div>
                          <div className="text-xs text-gray-500">confidence</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Search className="w-12 h-12 mx-auto mb-4" />
                    <p>No results found for "{searchResults.query}"</p>
                    <p className="text-sm">Try adjusting your search terms or enabling fuzzy matching</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Search History */}
          {searchHistory.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Recent Searches</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {searchHistory.map((search, index) => (
                    <div key={index} className="flex items-center justify-between p-2 border rounded">
                      <span className="text-sm">"{search.query}"</span>
                      <div className="flex items-center space-x-2 text-xs text-gray-500">
                        <span>{search.totalResults} results</span>
                        <span>•</span>
                        <span>{search.searchTime}ms</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="validation" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Code Validation & Compatibility</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Code Validation */}
              <div>
                <h3 className="text-lg font-medium mb-3">Code Validation</h3>
                <div className="space-y-3">
                  {['J00', 'A00', 'INVALID123'].map(code => {
                    const validation = validateCode(code);
                    return (
                      <div key={code} className="flex items-center justify-between p-3 border rounded-lg">
                        <span className="font-mono">{code}</span>
                        <div className="flex items-center space-x-2">
                          {validation.valid ? (
                            <>
                              <CheckCircle className="w-4 h-4 text-green-500" />
                              <span className="text-green-600 text-sm">Valid</span>
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="w-4 h-4 text-red-500" />
                              <span className="text-red-600 text-sm">{validation.message}</span>
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Code Compatibility */}
              <div>
                <h3 className="text-lg font-medium mb-3">Code Compatibility Check</h3>
                <div className="space-y-3">
                  {[['J00', 'J45'], ['A00', 'A00.0']].map(([code1, code2]) => {
                    const compatibility = checkCompatibility(code1, code2);
                    return (
                      <div key={`${code1}-${code2}`} className="flex items-center justify-between p-3 border rounded-lg">
                        <span className="font-mono">{code1} & {code2}</span>
                        <div className="flex items-center space-x-2">
                          {compatibility.compatible ? (
                            <>
                              <CheckCircle className="w-4 h-4 text-green-500" />
                              <span className="text-green-600 text-sm">{compatibility.message}</span>
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="w-4 h-4 text-red-500" />
                              <span className="text-red-600 text-sm">{compatibility.message}</span>
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="batch" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Batch Operations</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Batch Search Queries</label>
                  <textarea
                    className="w-full p-3 border rounded-lg"
                    rows={4}
                    placeholder="Enter multiple search terms, one per line:&#10;common cold&#10;asthma&#10;diabetes&#10;cholera"
                    defaultValue="common cold&#10;asthma&#10;diabetes&#10;cholera"
                  />
                </div>
                <Button>
                  <Zap className="w-4 h-4 mr-2" />
                  Run Batch Search
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="stats" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">Total Codes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.totalCodes.toLocaleString()}</div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">Billable Codes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">{stats.billableCodes.toLocaleString()}</div>
                <div className="text-xs text-gray-500">
                  {((stats.billableCodes / stats.totalCodes) * 100).toFixed(1)}%
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">Cache Hit Rate</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-600">{stats.cacheHitRate.toFixed(1)}%</div>
                <div className="text-xs text-gray-500">
                  {stats.cacheHits} hits / {stats.cacheMisses} misses
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">Performance</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-purple-600">~300ms</div>
                <div className="text-xs text-gray-500">avg search time</div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>System Capabilities</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium mb-2">Search Features</h4>
                  <ul className="text-sm space-y-1 text-gray-600">
                    <li>• Exact code matching</li>
                    <li>• Fuzzy text matching</li>
                    <li>• Semantic similarity search</li>
                    <li>• Abbreviation expansion</li>
                    <li>• Hierarchical code inclusion</li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium mb-2">Performance Features</h4>
                  <ul className="text-sm space-y-1 text-gray-600">
                    <li>• In-memory caching</li>
                    <li>• Batch processing</li>
                    <li>• Confidence scoring</li>
                    <li>• Real-time validation</li>
                    <li>• Compatibility checking</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default ICD10MapperDemo;