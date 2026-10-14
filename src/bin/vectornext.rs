use std::{env, path::Path};
use vectornext::{
    Database, Error, Result, backup,
    service::{Application, http, remote::Client},
};
fn run() -> Result<()> {
    let args: Vec<_> = env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("serve") if args.len() == 1 => {
            let path = env::var("VECTORNEXT_DATA").unwrap_or_else(|_| "/storage/db".into());
            let url = env::var("VECTORNEXT_PROCESSOR_URL")
                .unwrap_or_else(|_| "http://processor:8090".into());
            let address = env::var("VECTORNEXT_LISTEN").unwrap_or_else(|_| "0.0.0.0:8088".into());
            let weight = env::var("VECTORNEXT_GENERATED_WEIGHT")
                .unwrap_or_else(|_| "1".into())
                .parse()
                .map_err(|_| Error::Invalid("invalid generated weight".into()))?;
            let structural = env::var("VECTORNEXT_STRUCTURAL_WEIGHT")
                .unwrap_or_else(|_| "1".into())
                .parse()
                .map_err(|_| Error::Invalid("invalid structural weight".into()))?;
            let app = Application::open_with_weights(
                Path::new(&path),
                Client::new(url),
                structural,
                weight,
            )?;
            let _worker = app.start();
            http::serve(app, &address)
        }
        Some("export") if args.len() == 3 => {
            let manifest = Database::open(&args[1])?.export(Path::new(&args[2]))?;
            println!("{}", serde_json::to_string(&manifest)?);
            Ok(())
        }
        Some("restore") if args.len() == 3 => {
            let manifest = backup::restore(Path::new(&args[1]), Path::new(&args[2]))?;
            println!("{}", serde_json::to_string(&manifest)?);
            Ok(())
        }
        Some("inspect") if args.len() == 2 => {
            let db = Database::open(&args[1])?;
            println!(
                "{}",
                serde_json::json!({"generation":db.snapshot().generation(),"documents":db.snapshot().documents().collect::<Vec<_>>(),"jobs":db.ingestion_jobs()?})
            );
            Ok(())
        }
        _ => Err(Error::Invalid(
            "usage: vectornext serve | export DB NEW_BACKUP | restore BACKUP NEW_DB | inspect DB"
                .into(),
        )),
    }
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
