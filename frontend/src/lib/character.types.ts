/** 角色类型定义。 */

export interface Character {
  id: string;
  projectId: string;
  name: string;
  description: string;
  imageUrl: string | null;
  isFavorited: boolean;
  createdAt: string;
  updatedAt: string;
  relationshipCount: number;
}

export interface CharacterListItem {
  id: string;
  projectId: string;
  name: string;
  imageUrl: string | null;
  tokenCount: number;
  isFavorited: boolean;
  createdAt: string;
  updatedAt: string;
  relationshipCount: number;
}

export interface CharacterRelationship {
  id: string;
  sourceCharacterId: string;
  targetCharacterId: string;
  name: string;
  description: string;
}

export interface CharacterGraph {
  nodes: {
    characterId: string;
    name: string;
    imageUrl: string | null;
    x: number | null;
    y: number | null;
    relationshipCount: number;
  }[];
  relationships: CharacterRelationship[];
}

export interface CharacterCreate {
  name: string;
  description?: string;
  image?: File | null;
}

export interface CharacterUpdate {
  name?: string;
  description?: string;
  image?: File | null;
  isFavorited?: boolean;
}

export interface CharacterListResponse {
  items: CharacterListItem[];
  total: number;
}

export interface CharacterSearchMatch {
  lineNumber: number;
  lineText: string;
}

export interface CharacterSearchResult {
  characterId: string;
  characterName: string;
  matches: CharacterSearchMatch[];
}

export interface CharacterSearchResponse {
  results: CharacterSearchResult[];
  totalCharacters: number;
  totalMatches: number;
}
