import { create } from "zustand";

interface CharactersState {
  currentProjectId: string | null;
  currentCharacterId: string | null;
  isListOpen: boolean;
  setCurrentProject: (projectId: string | null) => void;
  setCurrentCharacter: (characterId: string | null) => void;
  setListOpen: (open: boolean) => void;
}

export const useCharactersStore = create<CharactersState>((set) => ({
  currentProjectId: null,
  currentCharacterId: null,
  isListOpen: false,
  setCurrentProject: (projectId) =>
    set({ currentProjectId: projectId, currentCharacterId: null }),
  setCurrentCharacter: (characterId) => set({ currentCharacterId: characterId }),
  setListOpen: (open) => set({ isListOpen: open }),
}));
