/**
 * File-path linkification for chat answers.
 * Detects patterns like `backend/foo/bar.py:1-9` and renders them as
 * clickable XP-blue links that copy the path to the clipboard.
 */

import React from "react";

// File extensions Bob's Claude tends to cite. Add more if we see misses.
const PATH_RE = /([a-zA-Z0-9_\-./]+\.(?:py|ts|tsx|js|jsx|md|mdx|json|sh|css|html|txt|yml|yaml|toml|rs|go|java|kt|swift|cpp|c|h)(?::\d+(?:-\d+)?)?)/g;

function copyPath(path) {
  try {
    navigator.clipboard.writeText(path);
  } catch {
    /* clipboard blocked — ignore */
  }
}

function linkifyString(text, keyBase) {
  // Quick reject if no `.` to avoid useless splits
  if (!text || text.indexOf(".") === -1) return text;
  const parts = text.split(PATH_RE);
  if (parts.length === 1) return text;
  return parts.map((p, i) =>
    i % 2 === 1 ? (
      <a
        key={`${keyBase}-${i}`}
        className="file-path-link"
        title="Click to copy path"
        href="#"
        onClick={(e) => {
          e.preventDefault();
          copyPath(p);
        }}
      >
        {p}
      </a>
    ) : (
      <React.Fragment key={`${keyBase}-${i}`}>{p}</React.Fragment>
    )
  );
}

function linkifyChildren(children) {
  return React.Children.map(children, (child, idx) => {
    if (typeof child === "string") return linkifyString(child, idx);
    return child;
  });
}

export const markdownComponents = {
  p: ({ children }) => <p>{linkifyChildren(children)}</p>,
  li: ({ children }) => <li>{linkifyChildren(children)}</li>,
  strong: ({ children }) => <strong>{linkifyChildren(children)}</strong>,
  em: ({ children }) => <em>{linkifyChildren(children)}</em>,
  code: ({ className, children }) => {
    const isBlock = typeof className === "string" && className.startsWith("language-");
    if (isBlock) {
      return (
        <pre className="xp-code-block">
          <code className={className}>{children}</code>
        </pre>
      );
    }
    return <code className="xp-inline-code">{linkifyChildren(children)}</code>;
  },
  a: ({ href, children }) => (
    <a className="md-link" href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
};
