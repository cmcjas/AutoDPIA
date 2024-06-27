import { useState } from 'react';
import { Document, Page } from 'react-pdf';

function PDFView(props: { fileLocation: string | null }) {
  const [numPages, setNumPages] = useState<number>();
  const [pageNumber, setPageNumber] = useState<number>(1);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }): void {
    setNumPages(numPages);
  }

  return (
    <div>
      <Document file={props.fileLocation} onLoadSuccess={onDocumentLoadSuccess}>
        <p>Page {pageNumber} of {numPages}</p>
        {Array.apply(null, Array(numPages))
            .map((x, i) => i + 1)
            .map((page) => {
                return (
                    <Page pageNumber={page} renderTextLayer={false} renderAnnotationLayer={false} width={1200}/>
                )
            }
        )
        }
      </Document>
    </div>
  );
}

export default PDFView;