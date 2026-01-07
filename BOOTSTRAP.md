1. Login via the `az` CLI
2. Copy `.env.local.example`, and set your subscription ID (`az account show | jq -r .id`)
3. (make sure you're using direnv, otherwise the last step literally does nothing)
4. Bootstrap the terraform state storage (only has to be done once in the entire project lifetime, don't delete the state or terraform will try to recreate everything):
    1. `cd terraform_bootstrap`
    2. Edit the configs, specifically `config_storage.auto.tfvars` and make sure you pick a unique `storage_account_name`
    3. `tofu init`
    4. `tofu apply`
5. (TODO) set up the CI
