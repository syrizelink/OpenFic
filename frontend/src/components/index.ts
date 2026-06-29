/**
 * Shared Components Module
 *
 * Shared UI components that are not feature-specific.
 */

export { ConfirmDialog } from "./confirm-dialog";
export { PromptChainDialog } from "./prompt-chain-dialog";
export type { PromptChainDialogEntry } from "./prompt-chain-dialog";
export { toast } from "./toast";
export { Toaster } from "./toaster";
export { ContextMenu } from "./context-menu";
export type { ContextMenuItem, ContextMenuPosition } from "./context-menu";
export { LabeledSelect, SearchableSelect, SimpleSelect } from "./select";
export type { SelectOption, LabeledSelectProps, SearchableSelectProps } from "./select";
export { TagInput } from "./tag-input";
export { AutocompletePopover } from "./autocomplete-popover";
export type { AutocompleteItem, AutocompletePopoverProps } from "./autocomplete-popover";
export { GlobalLoading } from "./global-loading";
export { Spinner } from "./spinner";
export type { SpinnerProps } from "./spinner";
export { ModelIdSelect } from "./model-id-select";
export type { ModelIdSelectOption } from "./model-id-select";
export { getModelValue } from "./model-id-select";
export { StreamingMarkdown } from "./streaming-markdown";
export { CircularProgress } from "./circular-progress";
export { MarkdownEditor } from "./markdown-editor";
export type { MarkdownEditorProps } from "./markdown-editor";
export { EditorToolbar } from "./editor-toolbar";
export type { EditorToolbarProps, EditorToolbarExtraAction } from "./editor-toolbar";
export { TitleInput } from "./title-input";
export type { TitleInputProps } from "./title-input";
export { createMarkdownEditorExtensions } from "./markdown-editor-config";
export type { MarkdownEditorExtensionsOptions } from "./markdown-editor-config";
export { createEditorShortcuts } from "./editor-shortcuts";
export type { EditorShortcutCallbacks } from "./editor-shortcuts";
export { ContentSearchPopover } from "./content-search-popover";
export type { ContentSearchMatch, ContentSearchResultItem } from "./content-search-popover";
