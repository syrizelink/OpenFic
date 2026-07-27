export function shouldShowCharacterEditorLoading(
  hasCharacter: boolean,
  isInitialLoading: boolean,
): boolean {
  return !hasCharacter && isInitialLoading;
}
