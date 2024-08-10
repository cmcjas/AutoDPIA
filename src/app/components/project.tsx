'use client'

import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Box, Checkbox, TextField } from "@mui/material";
import { useRef, useEffect, useState } from 'react'
import axios from 'axios';
import { Report } from "./report";

import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import DatasetIcon from '@mui/icons-material/Dataset';
import Grid from '@mui/material/Grid';


interface ProjProps {
    token: string | null;
}

const Project: React.FC<ProjProps> = ({ token }) => {

    const [projects, setProjects] = useState<{ projectID: number; title: string; description: string }[]>([]);
    const [selectedPrjs, setSelectedPrjs] = useState<number[]>([]);
    const [searchQuery, setSearchQuery] = useState<string>('');

    const [showTabs, setShowTabs] = useState(false);
    const [openDialog, setOpenDialog] = useState(false);
    const [projectTitle, setProjectTitle] = useState('');
    const [projectDescription, setProjectDescription] = useState('');

    const [projectID, setProjectID] = useState<number>(0);
    const [title, setTitle] = useState<string>('');
    const [description, setDescription] = useState<string>('');

    const chatParent = useRef<HTMLUListElement>(null)
    useEffect(() => {
        const domNode = chatParent.current
    })

    const filteredProjects = projects.filter(doc =>
        doc.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleSelectAll = () => {
        if (selectedPrjs.length === filteredProjects.length) {
          setSelectedPrjs([]);
        } else {
          setSelectedPrjs(filteredProjects.map(prj => prj.projectID));
        }
      };
    

    useEffect(() => {
        fetchProjects();
    }, [openDialog]);

    const fetchProjects = async () => {
        try {
            const res = await axios.get('http://localhost:8080/get_projects',
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );
            setProjects(res.data);

        } catch (error) {
            console.error('Error fetching documents:', error);
        }
    };

    const handleProjectDelete = async () => {
        try {
            const res = await axios.post('http://localhost:8080/delete_projects', selectedPrjs, {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                }
            });
            fetchProjects(); // Refresh the document list
            setSelectedPrjs([]); // Clear the selected documents

        } catch (error) {
            console.error('Error deleting documents:', error);
        }
    };


    const handleCheckboxChange = (event: React.ChangeEvent<HTMLInputElement>, prj: { projectID: number; title: string; description: string }) => {
        if (event.target.checked) {
            setSelectedPrjs([...selectedPrjs, prj.projectID]);
        } else {
            setSelectedPrjs(selectedPrjs.filter(id => id !== prj.projectID));
        }
    };

    // search logics
    const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchQuery(event.target.value);
    };

    const handleCreateProject = () => {
        setOpenDialog(true);
    };

    const handleCloseDialog = () => {
        setOpenDialog(false);
    };

    const handleSaveProject = async () => {
        // API call to save project details
        const projectData = {
            title: projectTitle,
            description: projectDescription
        }
        console.log('Sending project data:', projectData)
        const res = await axios.post('http://localhost:8080/create_project', projectData, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
        });

        if (res) {
            setOpenDialog(false);
        } else {
            // Handle error
            console.error('Failed to create project');
        }
    };

    const handleEnterProject = (projectID: number, title: string, description: string ) => {
        setProjectID(projectID);
        setTitle(title);
        setDescription(description);
        setShowTabs(true);
    };


    return (
        <main className="flex flex-col w-full h-screen max-h-dvh bg-background">
            
            <header className="p-4 border-b w-full h-16 bg-gradient-to-r from-purple-500 to-pink-500">
                <h1 className="text-3xl font-bold">PROJECT</h1>
            </header>
            <div className="p-4">
                {!showTabs ? (
                    <Button variant="contained" color="success" onClick={handleCreateProject}>Create Project</Button>
                ) : (
                    <Button variant="contained" color="primary" onClick={() => setShowTabs(false)}>Back</Button>
                )}
            </div>
            <section className="p-4 flex-1 overflow-auto" ref={chatParent} >
                {!showTabs ? ( 
                    <div>
                        <Box bgcolor="#e0e0e0" p={3} borderRadius={4} style={{ marginTop: '20px' }}>
                        <TextField
                            label="Search"
                            color="primary"
                            variant="outlined"
                            value={searchQuery}
                            onChange={handleSearchChange}
                            fullWidth
                            margin="normal"
                            style={{ margin: '15px 0', }}
                        />

                        {filteredProjects.length > 0 && (
                        <div>
                        <Button onClick={handleSelectAll} variant="contained" color="secondary">
                            {selectedPrjs.length === filteredProjects.length ? 'Deselect All' : 'Select All'}
                        </Button>
                        {selectedPrjs.length > 0 && (
                        <Button variant="contained" color="secondary" onClick={handleProjectDelete} style={{ marginLeft: '20px' }}>
                            Delete
                        </Button>
                        )}
                        </div>
                        )}
                        <Grid container spacing={2}>
                            <Grid item xs={12}>
                            
                            <List>
                                {filteredProjects.map(prj => (
                                    <ListItem key={prj.projectID} className="flex justify-between items-center"
                                        style={{ backgroundColor: '#ffffff', // White background for each item
                                            borderRadius: '4px', // Rounded corners for each item
                                            boxShadow: '0px 3px 6px rgba(0, 0, 0, 0.1)', // Light shadow to make items stand out
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            margin: '10px 0',
                                            alignItems: 'center', }}
                                    
                                    >
                                    <Checkbox
                                        checked={selectedPrjs.includes(prj.projectID)}
                                        onChange={(event) => handleCheckboxChange(event, prj)}
                                    />
                                        <ListItemIcon>
                                            <DatasetIcon fontSize="large"/>
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={prj.title}
                                        />
                                        <div >
                                            <Button variant="contained" color="primary" style={{ marginRight: '10px' }} onClick={() => handleEnterProject(prj.projectID, prj.title, prj.description)}>Enter</Button>
                                        </div>
                                    </ListItem>
                                ))}
                            </List>
                            </Grid>
                        </Grid>
                        </Box>
                    </div> 
                ) : (
                    <Report token={token} projectID={projectID} title={title} description={description}/>
                )}      
            </section>

            <Dialog open={openDialog} onClose={handleCloseDialog}>
                <DialogTitle>Create Project</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Project Title"
                        required
                        fullWidth
                        value={projectTitle}
                        onChange={(e) => setProjectTitle(e.target.value)}
                    />
                    <TextField
                        margin="dense"
                        label="Project Description"
                        fullWidth
                        value={projectDescription}
                        onChange={(e) => setProjectDescription(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleCloseDialog}>Cancel</Button>
                    <Button onClick={handleSaveProject} color="primary">Save Project</Button>
                </DialogActions>
            </Dialog>

        </main>
    );

}

export default Project;