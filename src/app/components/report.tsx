'use client'

import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Box, Checkbox, TextField } from "@mui/material";
import { Tab } from "@mui/material"
import { useEffect, useState } from 'react'
import axios from 'axios';
import { pdfjs } from 'react-pdf';
import PDFView from "./view";
import useToken from "../auth/token";
import { Dpia } from "./dpia";
import Snackbar, { SnackbarOrigin } from '@mui/material/Snackbar';
import { styled } from '@mui/material/styles';

import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import FolderIcon from '@mui/icons-material/Folder';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
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

const VisuallyHiddenInput = styled('input')({
    clip: 'rect(0 0 0 0)',
    clipPath: 'inset(50%)',
    height: 1,
    overflow: 'hidden',
    position: 'absolute',
    bottom: 0,
    left: 0,
    whiteSpace: 'nowrap',
    width: 1,
  });


export function Report(props: ReportProps) {

    const [activeTab, setActiveTab] = useState('files');
    const [uploadMessage, setUploadMessage] = useState('');

    const [open, setOpen] = useState(false);
    const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
    const [selectedDocName, setSelectedDocName] = useState<string | null>('');

    const [documents, setDocuments] = useState<{ fileID: number; fileName: string; }[]>([]);
    const [selectedDocs, setSelectedDocs] = useState<number[]>([]);
    const [searchQuery, setSearchQuery] = useState<string>('');

    const [selectedDpiaDocs, setSelectedDpiaDocs] = useState<number[]>([]);
    const [selectedDpiaDocName, setSelectedDpiaDocName] = useState<string[]>([]);

    const filteredDocuments = documents.filter(doc =>
        doc.fileName.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const projectID = props.projectID;
    const title = props.title;
    const description = props.description;
    const { token, removeToken, setToken } = useToken();



    const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        
        let selected_files: File[] = [];

        if (event.target.files) {
            selected_files = Array.from(event.target.files);
        }

        if (selected_files.length === 0) {
            setUploadMessage('No file selected');
            return;
        }

        const formData = new FormData();

        selected_files.forEach(async (file) => {
            // Upload each file
            formData.append('File', file);
        });

        formData.append('Mode', 'report')
        formData.append('projectID', projectID.toString());


        try {
            const res = await axios.post('http://localhost:8080/upload_doc', formData, {
                headers: {
                  'Content-Type': 'multipart/form-data',
                  'Authorization': `Bearer ${token}`
                }
              });


            if (res) {
                const sql = await axios.post('http://localhost:8080/toSQL', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                    'Authorization': `Bearer ${token}`
                }
                });
                setUploadMessage(`File(s) uploaded successfully`);
                fetchDocuments(); // Refresh the document list
                if (res.data.access_token) {
                    const new_token = res.data.access_token
                    setToken(new_token)
                }
                event.target.value = ''; // clear the input after uploading
            } else {
                setUploadMessage(`Error uploading file`);
            }
        } catch (error) {
            setUploadMessage(`Error uploading file`);
        }

    };

    const handleSelectAll = () => {
        if (selectedDocs.length === filteredDocuments.length) {
            setSelectedDocs([]);
        } else {
            setSelectedDocs(filteredDocuments.map(doc => doc.fileID));
        }
      };

    const handleSelectDpiaAll = () => {
        if (selectedDpiaDocs.length === filteredDocuments.length) {
            setSelectedDpiaDocs([]);
            setSelectedDpiaDocName([]);
        } else {
            setSelectedDpiaDocs(filteredDocuments.map(doc => doc.fileID));
            setSelectedDpiaDocName(filteredDocuments.map(doc => doc.fileName));
        }
    };
    

    useEffect(() => {
        fetchDocuments();
    }, []);

    const fetchDocuments = async () => {
        try {
            const res = await axios.get('http://localhost:8080/get_files', {params: { projectID: projectID }, 
                headers: {
                'Authorization': `Bearer ${token}`
            }
        });

            setDocuments(res.data);
            if (res.data.access_token) {
                const new_token = res.data.access_token
                setToken(new_token)
            }
        } catch (error) {
            console.error('Error fetching documents:', error);
        }
    };

    const handleFileDelete = async () => {
        try {
            const res = await axios.post('http://localhost:8080/delete_files', selectedDocs, {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
            });
            fetchDocuments(); // Refresh the document list
            setSelectedDocs([]); // Clear the selected documents
            if (res.data.access_token) {
                const new_token = res.data.access_token
                setToken(new_token)
            }
        } catch (error) {
            console.error('Error deleting documents:', error);
        }
    };

    const handleView = async (fileID: number, fileName: string,) => {
        setOpen(true);
        setSelectedDocName(fileName);

        
        const res = await axios.get(`http://localhost:8080/view_files/${fileID}?projectID=${projectID}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
            },
            responseType: 'blob'
        });
        const url = window.URL.createObjectURL(new Blob([res.data]));
        setSelectedDoc(url);

        if (res.data.access_token) {
            const new_token = res.data.access_token
            setToken(new_token)
        }

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

    const dpiaCheckboxChange = (event: React.ChangeEvent<HTMLInputElement>, doc: { fileID: number; fileName: string; }) => {
        if (event.target.checked) {
            setSelectedDpiaDocs([...selectedDpiaDocs, doc.fileID]);
            setSelectedDpiaDocName([...selectedDpiaDocName, doc.fileName]);
        } else {
            setSelectedDpiaDocs(selectedDpiaDocs.filter(id => id !== doc.fileID));
            setSelectedDpiaDocName(selectedDpiaDocName.filter(name => name !== doc.fileName));
        }
    };

    // search logics
    const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchQuery(event.target.value);
    };


    /* snackbar logics */
    interface State extends SnackbarOrigin {}
    const [state, setState] = React.useState<State>({
        vertical: 'top',
        horizontal: 'center',
      });
    const { vertical, horizontal } = state;


    return (
        <main className="flex flex-col w-full h-screen max-h-dvh bg-background">
            <Box bgcolor="#ededed" p={0.5} borderRadius={1} style={{ marginTop: '20px'}}>
                <header className="p-4 border-b w-full max-w-3xl mx-auto">
                    <h1 className="text-2xl font-bold">Project: {title}</h1>
                    <h2>{description}</h2>
                </header>
                    <Tab onClick={() => setActiveTab('files')} label='Files' style={{ backgroundColor: activeTab === 'files' ? '#1c1d1f' : 'transparent',
                     color: activeTab === 'files' ? 'white' : 'black' }}></Tab>
                    <Tab onClick={() => setActiveTab('reports')} label='Dpias' style={{ backgroundColor: activeTab === 'reports' ? '#1c1d1f' : 'transparent',
                     color: activeTab === 'reports' ? 'white' : 'black' }}></Tab>
            </Box>

            <section className="p-4 flex-1 overflow-auto">
                {activeTab === 'files' ? (
                    <div>
                        <Button
                            component="label"
                            variant="contained"
                            color="success"
                            tabIndex={-1}
                            startIcon={<CloudUploadIcon />}
                            style={{marginLeft: '10px', marginRight: '15px'}}
                        >
                            Upload
                            <VisuallyHiddenInput type="file" multiple onChange={handleFileChange} accept=".txt,.docx,.pdf" />
                        </Button>
                        <Box sx={{ width: 500 }}>
                        <Snackbar
                            anchorOrigin={{ vertical, horizontal }}
                            autoHideDuration={1000}
                            open={uploadMessage !== ''}
                            onClose={() => setUploadMessage('')}
                            message="File(s) uploaded successfully."
                            key={vertical + horizontal}
                        />
                        </Box>

                        <Box bgcolor="#e0e0e0" p={3} borderRadius={4} style={{ marginTop: '20px' }}>
                        <TextField
                            label="Search"
                            color="primary"
                            variant="outlined"
                            value={searchQuery}
                            onChange={handleSearchChange}
                            fullWidth
                            style={{ margin: '15px 0', }}
                        />

                        {filteredDocuments.length > 0 && (
                        <div>
                        <Button onClick={handleSelectAll} variant="contained" color="secondary" >
                            {selectedDocs.length === filteredDocuments.length ? 'Deselect All' : 'Select All'}
                        </Button>
                        <Button onClick={handleSelectDpiaAll} variant="contained" color="secondary" style={{ marginLeft: '20px' }}>
                            {selectedDpiaDocs.length === filteredDocuments.length ? 'Deselect All Dpia Files' : 'Select All Dpia Files'}
                        </Button>
                        {selectedDocs.length > 0 && (
                        <Button variant="contained" color="secondary" onClick={handleFileDelete} style={{ marginLeft: '20px' }}>
                            Delete
                        </Button>
                        )}
                        </div>
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
                                            margin: '10px 0',
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
                                    <Checkbox
                                        checked={selectedDpiaDocs.includes(doc.fileID)}
                                        onChange={(event) => dpiaCheckboxChange(event, doc)}
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
                    <Dpia projectID={projectID} dpiaFileNames={selectedDpiaDocName}/>
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