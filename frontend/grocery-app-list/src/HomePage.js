import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import API_BASE_URL from "./config";
import { Container, TextField, Typography, Paper, IconButton, List, ListItem, ListItemText, Grid, Card, CardContent, CardMedia, Button, Divider, Box, Collapse } from "@mui/material";
import { Delete, LocationOn, ExpandMore, ExpandLess } from "@mui/icons-material";
import StoreComparisonCard from "./StoreComparisonCard";

const HomePage = () => {
  const [stores, setStores] = useState([]);
  const [userZip, setUserZip] = useState("");
  const [groceryList, setGroceryList] = useState(() => JSON.parse(localStorage.getItem('groceryList')) || []);
  const [newItem, setNewItem] = useState("");
  const [showComparison, setShowComparison] = useState(false);
  const [comparisons, setComparisons] = useState({ items: [], totalBestPrice: 0 });
  const [sortByDistance, setSortByDistance] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [optimizedStops, setOptimizedStops] = useState(null);
  const [optimizing, setOptimizing] = useState(false);
  const [showPriceComparison, setShowPriceComparison] = useState(true);
  const [showOptimization, setShowOptimization] = useState(true);

  const navigate = useNavigate();

  useEffect(() => {
    localStorage.setItem('groceryList', JSON.stringify(groceryList));
  }, [groceryList]);

  const fetchStores = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = userZip && sortByDistance
        ? `${API_BASE_URL}/stores/by-distance/${userZip}`
        : `${API_BASE_URL}/stores`;

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch stores');
      const data = await response.json();
      setStores(data);
    } catch (err) {
      setError('Failed to load stores. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStores();
  }, [userZip, sortByDistance]);

  const handleCompareClick = async () => {
    if (groceryList.length === 0) return alert("Please add items to your grocery list first!");

    try {
      const response = await fetch(`${API_BASE_URL}/api/compare-prices`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: groceryList, userZip })
      });
      if (!response.ok) throw new Error('Failed to fetch price comparisons');

      const data = await response.json();
      setComparisons(data);
      setShowComparison(true);
    } catch (error) {
      alert("Error comparing prices. Please try again.");
    }
  };

  const handleOptimizeStops = async () => {
    if (groceryList.length === 0) return alert("Please add items to your grocery list first!");
    if (!userZip) return alert("Please enter your ZIP code to optimize shopping stops!");

    setOptimizing(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/optimize-stops`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: groceryList, userZip })
      });
      if (!response.ok) throw new Error('Failed to optimize shopping stops');

      const data = await response.json();
      setOptimizedStops(data);
    } catch (error) {
      alert("Error optimizing shopping stops. Please try again.");
    } finally {
      setOptimizing(false);
    }
  };

  const handleAddItem = () => {
    if (newItem.trim() && !groceryList.includes(newItem.trim())) {
      setGroceryList([...groceryList, newItem.trim()]);
      setNewItem("");
    }
  };

  const handleRemoveItem = (item) => {
    const updatedList = groceryList.filter(i => i !== item);
    setGroceryList(updatedList);
    if (updatedList.length <= 1) setShowComparison(false);
  };

  const handleClearList = () => {
    setGroceryList([]);
    setShowComparison(false);
    setComparisons({ items: [], totalBestPrice: 0 });
    setOptimizedStops(null);
  };

  const formatProductName = (name) => name.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 6, minHeight: '100vh', bgcolor: '#f9f9f9', py: 4 }}>
      <Typography variant="h4" align="center" sx={{ mb: 4, fontWeight: 600, color: '#3c3c3c' }}>
        Grocery Smart 🛒
      </Typography>

      <Paper elevation={0} sx={{ p: 3, mb: 4, borderRadius: 2, border: '1px solid #ddd', bgcolor: '#fff' }}>
        <TextField
          size="small"
          label="ZIP Code (Optional)"
          type="text"
          value={userZip}
          onChange={(e) => setUserZip(e.target.value)}
          fullWidth
          sx={{ mb: 2 }}
        />

        <TextField
          fullWidth
          label="Add Item"
          value={newItem}
          onChange={(e) => setNewItem(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAddItem()}
          size="small"
        />
        <Button
          variant="contained"
          fullWidth
          onClick={handleAddItem}
          disabled={!newItem.trim()}
          sx={{ mt: 2, backgroundColor: '#6fcf97', '&:hover': { backgroundColor: '#57ae81' } }}
        >
          Add Item
        </Button>

        {groceryList.length > 0 && (
          <>
            <List>
              {groceryList.map((item, index) => (
                <ListItem key={index} secondaryAction={
                  <IconButton onClick={() => handleRemoveItem(item)}>
                    <Delete />
                  </IconButton>
                }>
                  <ListItemText primary={formatProductName(item)} />
                </ListItem>
              ))}
            </List>

            <Button
              variant="outlined"
              fullWidth
              onClick={handleCompareClick}
              sx={{ mt: 2 }}
            >
              Compare Prices
            </Button>

            {userZip && (
              <Button
                variant="outlined"
                fullWidth
                onClick={handleOptimizeStops}
                disabled={optimizing}
                sx={{ mt: 1 }}
              >
                {optimizing ? "Optimizing..." : "Optimize Shopping Stops"}
              </Button>
            )}

            <Button
              variant="text"
              color="error"
              fullWidth
              onClick={handleClearList}
              sx={{ mt: 1 }}
            >
              Clear List
            </Button>
          </>
        )}
      </Paper>

      {/* Comparison Results */}
      {showComparison && (
        <Paper elevation={0} sx={{ p: 3, mb: 4, borderRadius: 2, border: '1px solid #ddd', bgcolor: '#fff' }}>
          <Box onClick={() => setShowPriceComparison(!showPriceComparison)} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', mb: 2 }}>
            <Typography variant="h6" sx={{ color: '#3c3c3c' }}>Price Comparison Results</Typography>
            <IconButton>
              {showPriceComparison ? <ExpandLess /> : <ExpandMore />}
            </IconButton>
          </Box>
          <Collapse in={showPriceComparison}>
            <StoreComparisonCard comparisons={comparisons} />
          </Collapse>
        </Paper>
      )}

      {/* Store Listing */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6" sx={{ color: '#3c3c3c' }}>Available Stores</Typography>
        {userZip && (
          <Button variant="outlined" size="small" onClick={() => setSortByDistance(!sortByDistance)}>
            {sortByDistance ? "Default Order" : "Sort by Distance"}
          </Button>
        )}
      </Box>

      {error && <Typography color="error">{error}</Typography>}
      {loading ? (
        <Typography align="center">Loading stores...</Typography>
      ) : (
        <Grid container spacing={3}>
          {stores.map(store => (
            <Grid item xs={12} sm={6} md={4} key={store.id}>
              <Card onClick={() => navigate(`/store/${store.id}`)} sx={{ cursor: 'pointer', borderRadius: 2, boxShadow: 1, transition: "0.3s", '&:hover': { boxShadow: 3 } }}>
                <CardMedia component="img" height="140" image={`/images/stores/${store.id}.png`} alt={store.name} />
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>{store.name}</Typography>
                  <Typography variant="body2" color="text.secondary">ZIP: {store.zip_code}</Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Container>
  );
};

export default HomePage;
