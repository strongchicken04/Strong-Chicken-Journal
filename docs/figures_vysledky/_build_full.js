// Full-paper builder. Reads content_full.js -> writes one .docx.
// Supports: titlepage, subtitle, author, h1/h2/h3, p, b(bullet), table, img+caption,
// caption, refs (numbered hanging), pagebreak. Inline **bold** and ^superscript^.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, ImageRun, Table, TableRow,
  TableCell, WidthType, AlignmentType, BorderStyle, LevelFormat, ShadingType, PageBreak,
} = require("docx");

const ROOT = "/home/user/Strong-Chicken-Journal";
const content = require(path.join(__dirname, process.argv[2]));
const outFile = process.argv[3];

function pngSize(file) {
  const b = fs.readFileSync(file);
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}

// parse **bold** and ^superscript^ into TextRuns
function runs(text, extra = {}) {
  const out = [];
  String(text).split(/(\*\*[^*]+\*\*|\^[^^]+\^)/).forEach((seg) => {
    if (!seg) return;
    if (seg.startsWith("**") && seg.endsWith("**"))
      out.push(new TextRun({ text: seg.slice(2, -2), bold: true, italics: extra.italics, size: extra.size, color: extra.color }));
    else if (seg.startsWith("^") && seg.endsWith("^"))
      out.push(new TextRun({ text: seg.slice(1, -1), superScript: true, size: extra.size, color: extra.color }));
    else
      out.push(new TextRun({ text: seg, bold: extra.bold, italics: extra.italics, size: extra.size, color: extra.color }));
  });
  return out.length ? out : [new TextRun({ text: "" })];
}

const children = [];
for (const item of content) {
  const [type, a, b] = item;
  if (type === "titlepage") {
    children.push(new Paragraph({ children: runs(a, { bold: true, size: 44 }), alignment: AlignmentType.CENTER, spacing: { before: 2600, after: 240 } }));
  } else if (type === "subtitle") {
    children.push(new Paragraph({ children: runs(a, { size: 26, color: "555555" }), alignment: AlignmentType.CENTER, spacing: { after: 160 } }));
  } else if (type === "author") {
    children.push(new Paragraph({ children: runs(a, { size: 22 }), alignment: AlignmentType.CENTER, spacing: { after: 120 } }));
  } else if (type === "h1") {
    children.push(new Paragraph({ children: runs(a, { bold: true, size: 30, color: "1F3864" }), heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 150 } }));
  } else if (type === "h2") {
    children.push(new Paragraph({ children: runs(a, { bold: true, size: 25, color: "2E5496" }), heading: HeadingLevel.HEADING_2, spacing: { before: 260, after: 110 } }));
  } else if (type === "h3") {
    children.push(new Paragraph({ children: runs(a, { bold: true, size: 22, color: "2E5496" }), spacing: { before: 200, after: 90 } }));
  } else if (type === "p") {
    children.push(new Paragraph({ children: runs(a), spacing: { after: 140, line: 276 }, alignment: AlignmentType.JUSTIFIED }));
  } else if (type === "b") {
    children.push(new Paragraph({ children: runs(a), numbering: { reference: "bul", level: 0 }, spacing: { after: 70, line: 264 }, alignment: AlignmentType.JUSTIFIED }));
  } else if (type === "quote") {
    children.push(new Paragraph({ children: runs(a, { italics: true }), indent: { left: 460 }, spacing: { after: 150 }, border: { left: { style: BorderStyle.SINGLE, size: 18, color: "888888", space: 8 } } }));
  } else if (type === "img") {
    const file = path.isAbsolute(a) ? a : path.join(ROOT, a);
    if (!fs.existsSync(file)) { children.push(new Paragraph({ children: runs(`[[ chybí obrázek: ${a} ]]`, { italics: true, color: "C0392B" }), alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 } })); }
    else {
      const [w0, h0] = pngSize(file);
      const w = 560, h = Math.round((h0 * 560) / w0);
      children.push(new Paragraph({ children: [new ImageRun({ data: fs.readFileSync(file), transformation: { width: w, height: h }, type: "png" })], alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 } }));
    }
    if (b) children.push(new Paragraph({ children: runs(b, { italics: true, size: 17, color: "555555" }), alignment: AlignmentType.CENTER, spacing: { after: 220 } }));
  } else if (type === "caption") {
    children.push(new Paragraph({ children: runs(a, { italics: true, size: 17, color: "555555" }), alignment: AlignmentType.CENTER, spacing: { after: 200 } }));
  } else if (type === "placeholder") {
    children.push(new Paragraph({ children: runs(a, { italics: true, color: "8a6d00", size: 19 }), alignment: AlignmentType.CENTER, spacing: { before: 160, after: 40 }, border: { top: { style: BorderStyle.DASHED, size: 8, color: "C9A227", space: 8 }, bottom: { style: BorderStyle.DASHED, size: 8, color: "C9A227", space: 8 }, left: { style: BorderStyle.DASHED, size: 8, color: "C9A227", space: 8 }, right: { style: BorderStyle.DASHED, size: 8, color: "C9A227", space: 8 } } }));
    if (b) children.push(new Paragraph({ children: runs(b, { italics: true, size: 17, color: "555555" }), alignment: AlignmentType.CENTER, spacing: { after: 220 } }));
  } else if (type === "table") {
    const rowsData = a, ncols = rowsData[0].length, total = 9360, cw = Math.floor(total / ncols);
    const rows = rowsData.map((r, ri) => new TableRow({ children: r.map((cell) => new TableCell({ width: { size: cw, type: WidthType.DXA }, shading: ri === 0 ? { type: ShadingType.CLEAR, fill: "E8EEF4" } : undefined, margins: { top: 60, bottom: 60, left: 100, right: 100 }, children: [new Paragraph({ children: runs(String(cell), { bold: ri === 0, size: 19 }) })] })) }));
    children.push(new Table({ columnWidths: Array(ncols).fill(cw), width: { size: total, type: WidthType.DXA }, rows }));
    children.push(new Paragraph({ text: "", spacing: { after: 140 } }));
  } else if (type === "refs") {
    a.forEach((e, i) => children.push(new Paragraph({ children: runs(`(${i + 1})\t` + e), spacing: { after: 150, line: 264 }, alignment: AlignmentType.JUSTIFIED, indent: { left: 567, hanging: 567 }, tabStops: [{ type: "left", position: 567 }] })));
  } else if (type === "pagebreak") {
    children.push(new Paragraph({ children: [new PageBreak()] }));
  }
}

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 460, hanging: 260 } } } }] }] },
  styles: { default: { document: { run: { font: "Calibri", size: 22 } } } },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1200, bottom: 1200, left: 1300, right: 1300 } } }, children }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outFile, buf); console.log("written", outFile, buf.length, "bytes"); });
