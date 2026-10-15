use vectornext::{
    Database,
    search::{KeywordConfig, SearchIndex},
};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args().nth(1).ok_or("database path required")?;
    let db = Database::open(path)?;
    let snapshot = db.snapshot();
    let space = snapshot.spaces().next().ok_or("space missing")?.0.clone();
    let index = SearchIndex::build(snapshot, space, KeywordConfig::default())?;
    println!("{}", serde_json::to_string(index.filter_index_stats())?);
    Ok(())
}
