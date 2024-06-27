'use client'

import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Box, Checkbox, TextField } from "@mui/material";
import { Tab } from "@mui/material"
import { useRef, useEffect, useState } from 'react'
import axios from 'axios';
import { pdfjs, Document, Page } from 'react-pdf';
import PDFView from "./view";

import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import FolderIcon from '@mui/icons-material/Folder';
import Grid from '@mui/material/Grid';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
  ).toString();
  

import React from 'react';

interface ReportProps {
  projectID: number;
  title: string;
  description: string;
}

export function Report(props: ReportProps) {

    const [activeTab, setActiveTab] = useState('files');
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [uploadMessage, setUploadMessage] = useState('');

    const [open, setOpen] = useState(false);
    const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
    const [selectedDocName, setSelectedDocName] = useState<string | null>('');

    const [documents, setDocuments] = useState<{ fileID: number; fileName: string; }[]>([]);
    const [selectedDocs, setSelectedDocs] = useState<number[]>([]);
    const [searchQuery, setSearchQuery] = useState<string>('');

    const filteredDocuments = documents.filter(doc =>
        doc.fileName.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const projectID = props.projectID;
    const title = props.title;
    const description = props.description;


    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files) {
            setSelectedFiles(Array.from(event.target.files));
        }
    };

    const handleSelectAll = () => {
        if (selectedDocs.length === filteredDocuments.length) {
          setSelectedDocs([]);
        } else {
          setSelectedDocs(filteredDocuments.map(doc => doc.fileID));
        }
      };
    
    const handleUpload = async () => {
        if (selectedFiles.length === 0) {
            setUploadMessage('No file selected');
            return;
        }

        const formData = new FormData();

        selectedFiles.forEach(async (file) => {
            // Upload each file
            formData.append('File', file);
        });

        formData.append('Mode', 'report')
        formData.append('projectID', projectID.toString());


        try {
            const res = await axios.post('http://localhost:8080/upload_doc', formData, {
                headers: {
                  'Content-Type': 'multipart/form-data'
                }
              });

            if (res) {
                const sql = await axios.post('http://localhost:8080/toSQL', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
                });
                setUploadMessage(`File(s) uploaded successfully`);
                fetchDocuments(); // Refresh the document list
            } else {
                setUploadMessage(`Error uploading file`);
            }
        } catch (error) {
            setUploadMessage(`Error uploading file`);
        }
    };


    useEffect(() => {
        fetchDocuments();
    }, []);

    const fetchDocuments = async () => {
        try {
            const res = await axios.get('http://localhost:8080/get_files', {params: { projectID: projectID }});

            setDocuments(res.data);
        } catch (error) {
            console.error('Error fetching documents:', error);
        }
    };

    const handleFileDelete = async () => {
        try {
            const response = await fetch('http://localhost:8080/delete_files', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ selectedDocs }), // Make sure the key here matches what the backend expects
            });
            fetchDocuments(); // Refresh the document list
            setSelectedDocs([]); // Clear the selected documents
        } catch (error) {
            console.error('Error deleting documents:', error);
        }
    };

    const handleView = (fileID: number, fileName: string,) => {
        setOpen(true);
        setSelectedDoc(`http://localhost:8080/view_files/${fileID}?projectID=${projectID}`);
        setSelectedDocName(fileName);
    };

    const handleClose = () => {
        setOpen(false);
    };


    const handleCheckboxChange = (event: React.ChangeEvent<HTMLInputElement>, doc: { fileID: number; fileName: string; }) => {
        if (event.target.checked) {
            setSelectedDocs([...selectedDocs, doc.fileID]);
        } else {
            setSelectedDocs(selectedDocs.filter(id => id !== doc.fileID));
        }
    };

    // search logics
    const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchQuery(event.target.value);
    };



    return (
        <main className="flex flex-col w-full h-screen max-h-dvh bg-background">
            <Box bgcolor="#ededed" p={0.5} borderRadius={1} style={{ marginTop: '20px' }}>
                <header className="p-4 border-b w-full max-w-3xl mx-auto">
                    <h1 className="text-2xl font-bold">Project: {title}</h1>
                    <h2>{description}</h2>
                </header>

                    <Tab onClick={() => setActiveTab('files')} label='Files'></Tab>
                    <Tab onClick={() => setActiveTab('reports')} label='Reports'></Tab>

            </Box>

            <section className="p-4 w-full max-w-3xl mx-auto">
                {activeTab === 'files' ? (
                    <div>
                        <input type="file" multiple onChange={handleFileChange} />
                        <Button onClick={handleUpload} variant="contained" color="success" >Upload</Button>
                        {uploadMessage && <p>{uploadMessage}</p>}

                        <Box bgcolor="#e0e0e0" p={3} borderRadius={4} style={{ marginTop: '20px' }}>
                        <TextField
                            label="Search"
                            color="primary"
                            variant="outlined"
                            value={searchQuery}
                            onChange={handleSearchChange}
                            fullWidth
                            margin="normal"
                        />
                        {selectedDocs.length > 0 && (
                        <Button variant="contained" color="secondary" onClick={handleFileDelete}>
                            Delete
                        </Button>
                        )}

                        {filteredDocuments.length > 0 && (
                        <Button onClick={handleSelectAll} variant="contained" color="secondary" style={{ marginLeft: '20px' }}>
                            {selectedDocs.length === filteredDocuments.length ? 'Deselect All' : 'Select All'}
                        </Button>
                        )}
                        <Grid container spacing={2}>
                            <Grid item xs={12}>
                            
                            <List>
                                {filteredDocuments.map(doc => (
                                    <ListItem key={doc.fileID} className="flex justify-between items-center"
                                        style={{ backgroundColor: '#ffffff', // White background for each item
                                            borderRadius: '4px', // Rounded corners for each item
                                            boxShadow: '0px 3px 6px rgba(0, 0, 0, 0.1)', // Light shadow to make items stand out
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            margin: '15px 0',
                                            alignItems: 'center', }}
                                    
                                    >
                                    <Checkbox
                                        checked={selectedDocs.includes(doc.fileID)}
                                        onChange={(event) => handleCheckboxChange(event, doc)}
                                    />
                                        <ListItemIcon>
                                            <FolderIcon fontSize="large"/>
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={doc.fileName}
                                        />
                                        <div >
                                            <Button onClick={() => handleView(doc.fileID, doc.fileName)} variant="contained" color="primary" style={{ marginRight: '10px' }}>View</Button>
                                        </div>
                                    </ListItem>
                                ))}
                            </List>
                            </Grid>
                        </Grid>
                        </Box>
                    </div>
                    
                ) : (
                    <div>Hello Reports</div>
                )}
            </section>
            <Dialog open={open} onClose={handleClose}  fullWidth maxWidth="lg">
                <DialogTitle>{selectedDocName}</DialogTitle>
                <DialogContent>
                    <PDFView fileLocation={selectedDoc} />
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleClose} color="primary">
                        Close
                    </Button>
                </DialogActions>
            </Dialog>
        </main>
    );

}