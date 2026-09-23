import cIcon from "@iconify-icons/material-icon-theme/c";
import cppIcon from "@iconify-icons/material-icon-theme/cpp";
import csharpIcon from "@iconify-icons/material-icon-theme/csharp";
import cssIcon from "@iconify-icons/material-icon-theme/css";
import dartIcon from "@iconify-icons/material-icon-theme/dart";
import dockerIcon from "@iconify-icons/material-icon-theme/docker";
import documentIcon from "@iconify-icons/material-icon-theme/document";
import elixirIcon from "@iconify-icons/material-icon-theme/elixir";
import epubIcon from "@iconify-icons/material-icon-theme/epub";
import erlangIcon from "@iconify-icons/material-icon-theme/erlang";
import goIcon from "@iconify-icons/material-icon-theme/go";
import haskellIcon from "@iconify-icons/material-icon-theme/haskell";
import htmlIcon from "@iconify-icons/material-icon-theme/html";
import imageIcon from "@iconify-icons/material-icon-theme/image";
import javaIcon from "@iconify-icons/material-icon-theme/java";
import javascriptIcon from "@iconify-icons/material-icon-theme/javascript";
import jsonIcon from "@iconify-icons/material-icon-theme/json";
import logIcon from "@iconify-icons/material-icon-theme/log";
import luaIcon from "@iconify-icons/material-icon-theme/lua";
import markdownIcon from "@iconify-icons/material-icon-theme/markdown";
import nginxIcon from "@iconify-icons/material-icon-theme/nginx";
import objectiveCIcon from "@iconify-icons/material-icon-theme/objective-c";
import objectiveCppIcon from "@iconify-icons/material-icon-theme/objective-cpp";
import pdfIcon from "@iconify-icons/material-icon-theme/pdf";
import perlIcon from "@iconify-icons/material-icon-theme/perl";
import phpIcon from "@iconify-icons/material-icon-theme/php";
import powerpointIcon from "@iconify-icons/material-icon-theme/powerpoint";
import powershellIcon from "@iconify-icons/material-icon-theme/powershell";
import pythonIcon from "@iconify-icons/material-icon-theme/python";
import rIcon from "@iconify-icons/material-icon-theme/r";
import rubyIcon from "@iconify-icons/material-icon-theme/ruby";
import rustIcon from "@iconify-icons/material-icon-theme/rust";
import scalaIcon from "@iconify-icons/material-icon-theme/scala";
import svelteIcon from "@iconify-icons/material-icon-theme/svelte";
import swiftIcon from "@iconify-icons/material-icon-theme/swift";
import tableIcon from "@iconify-icons/material-icon-theme/table";
import tomlIcon from "@iconify-icons/material-icon-theme/toml";
import typescriptIcon from "@iconify-icons/material-icon-theme/typescript";
import vueIcon from "@iconify-icons/material-icon-theme/vue";
import wordIcon from "@iconify-icons/material-icon-theme/word";
import xmlIcon from "@iconify-icons/material-icon-theme/xml";
import yamlIcon from "@iconify-icons/material-icon-theme/yaml";
import zipIcon from "@iconify-icons/material-icon-theme/zip";
import { Icon } from "@iconify/react/offline";
import { Box, Tooltip } from "@radix-ui/themes";
import { Info, X } from "lucide-react";

import { formatAgentFileSize, getAgentFileExtension } from "../../lib/agent-file-attachments";

interface AgentFileAttachmentCardProps {
  fileName: string;
  mimeType?: string;
  sizeBytes: number;
  isProcessing?: boolean;
  onRemove?: () => void;
  removeLabel?: string;
  extractingLabel?: string;
  error?: string;
}

function getFileKind(
  fileName: string,
  mimeType?: string,
): "document" | "code" | "spreadsheet" | "presentation" {
  const extension = getAgentFileExtension(fileName).toLowerCase();
  if (["csv", "xls", "xlsx"].includes(extension) || mimeType?.includes("spreadsheet")) {
    return "spreadsheet";
  }
  if (["ppt", "pptx"].includes(extension) || mimeType?.includes("presentation")) {
    return "presentation";
  }
  if (
    [
      "bash",
      "bat",
      "c",
      "cpp",
      "css",
      "cs",
      "dart",
      "go",
      "h",
      "hpp",
      "java",
      "js",
      "jsx",
      "lua",
      "php",
      "py",
      "rb",
      "rs",
      "sh",
      "sql",
      "swift",
      "ts",
      "tsx",
      "vue",
    ].includes(extension)
  ) {
    return "code";
  }
  return "document";
}

const FILE_ICONS: Record<string, typeof documentIcon> = {
  bash: documentIcon,
  bat: documentIcon,
  c: cIcon,
  cmd: documentIcon,
  conf: documentIcon,
  cpp: cppIcon,
  css: cssIcon,
  csv: tableIcon,
  cs: csharpIcon,
  dart: dartIcon,
  db2: documentIcon,
  doc: wordIcon,
  docx: wordIcon,
  dockerfile: dockerIcon,
  epub: epubIcon,
  erl: erlangIcon,
  ex: elixirIcon,
  exs: elixirIcon,
  go: goIcon,
  h: cIcon,
  hpp: cppIcon,
  hs: haskellIcon,
  hsc: haskellIcon,
  html: htmlIcon,
  htm: htmlIcon,
  ini: documentIcon,
  java: javaIcon,
  js: javascriptIcon,
  jsx: javascriptIcon,
  json: jsonIcon,
  lhs: haskellIcon,
  log: logIcon,
  lua: luaIcon,
  m: objectiveCIcon,
  md: markdownIcon,
  mm: objectiveCppIcon,
  nginxconf: nginxIcon,
  odt: documentIcon,
  pdf: pdfIcon,
  perl: perlIcon,
  php: phpIcon,
  pl: perlIcon,
  pm: perlIcon,
  ppt: powerpointIcon,
  pptx: powerpointIcon,
  ps1: powershellIcon,
  py: pythonIcon,
  rb: rubyIcon,
  rs: rustIcon,
  rst: markdownIcon,
  r: rIcon,
  scala: scalaIcon,
  sh: documentIcon,
  sql: documentIcon,
  svelte: svelteIcon,
  swift: swiftIcon,
  toml: tomlIcon,
  ts: typescriptIcon,
  tsx: typescriptIcon,
  txt: documentIcon,
  vue: vueIcon,
  webp: imageIcon,
  xls: tableIcon,
  xlsx: tableIcon,
  xml: xmlIcon,
  yaml: yamlIcon,
  yml: yamlIcon,
  zip: zipIcon,
};

function getFileIcon(fileName: string, mimeType?: string) {
  const extension = getAgentFileExtension(fileName).toLowerCase();
  if (FILE_ICONS[extension]) return FILE_ICONS[extension];
  if (mimeType?.includes("spreadsheet")) return tableIcon;
  if (mimeType?.includes("presentation")) return powerpointIcon;
  if (mimeType?.startsWith("image/")) return imageIcon;
  if (mimeType?.startsWith("text/")) return documentIcon;
  return documentIcon;
}

export function AgentFileAttachmentCard({
  fileName,
  mimeType,
  sizeBytes,
  isProcessing = false,
  onRemove,
  removeLabel,
  extractingLabel,
  error,
}: AgentFileAttachmentCardProps) {
  const fileKind = getFileKind(fileName, mimeType);
  const fileIcon = getFileIcon(fileName, mimeType);
  const className = [
    "agent-file-attachment-card",
    onRemove && "agent-file-attachment-card--removable",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={className}
      data-file-kind={fileKind}
    >
      <span
        className="agent-file-attachment-icon"
        aria-hidden="true"
      >
        {isProcessing ? (
          <span
            className="agent-file-attachment-icon-spinner"
            aria-label={extractingLabel}
          >
            <span className="agent-file-attachment-spinner-dot" />
          </span>
        ) : (
          <Icon
            icon={fileIcon}
            width={24}
            height={24}
          />
        )}
      </span>
      <span className="agent-file-attachment-details">
        <span
          className={
            error
              ? "agent-file-attachment-name agent-file-attachment-name--error"
              : "agent-file-attachment-name"
          }
        >
          <Tooltip content={fileName}>
            <span className="agent-file-attachment-name-text">{fileName}</span>
          </Tooltip>
          {error ? (
            <Tooltip content={<Box className="agent-file-attachment-error-tooltip">{error}</Box>}>
              <span
                className="agent-file-attachment-error-info"
                role="img"
                aria-label={error}
                tabIndex={0}
              >
                <Info size={14} />
              </span>
            </Tooltip>
          ) : null}
        </span>
        <span className="agent-file-attachment-meta">
          {getAgentFileExtension(fileName)} {formatAgentFileSize(sizeBytes)}
        </span>
      </span>
      {onRemove ? (
        <button
          type="button"
          className="agent-file-attachment-remove"
          aria-label={removeLabel}
          onClick={onRemove}
        >
          <X size={13} />
        </button>
      ) : null}
    </div>
  );
}
